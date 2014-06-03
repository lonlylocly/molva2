#!/usr/bin/python
# -*- coding: UTF-8 -*-
import tornado.ioloop
import tornado.web
import sys
import os
import json
import time
import re
import logging
from subprocess import check_output
import sqlite3

import KMeanCluster
import stats
from StatsDisplay import StatsDisplay
from Indexer import Indexer

#logging.config.fileConfig("logging.conf")

settings = json.load(open('handler-settings.json', 'r'))

logging.config.fileConfig("logging.conf")

class GuessrHandler(tornado.web.RequestHandler):
    def get(self):
        try:
            title = self.get_argument("title", default="")
            title = re.sub("(\n|\t)", " ", title)
            title = re.sub("\"", "\\\"", title)

            ind = Indexer(settings["db_dir"])
            db_filename = ind.dates_dbs["20140525"]
            con = sqlite3.connect(db_filename)
            con.isolation_level = None
            cur = con.cursor()

            context = stats.get_sim_nouns_by_context(cur, title) 
            nouns = stats.get_nouns(cur, nouns_only = map(lambda x: x["noun_md5"], context))
            for c in context:
                c["noun_text"] = nouns[c["noun_md5"]]

            sim_docs = None 
            if len(context) != 0:
                stats.create_given_tables(cur, ["titles", "titles_profiles"])

                stats.save_title_context(cur, title, context)

                sim_docs = stats.get_similar_titles(cur, title, context) 
            
            self.write(json.dumps({"profile": context, "sim_docs": sim_docs}, indent=4))

            con.close()

        except Exception as e:
            logging.error(e)
            raise e

class DatesAvailableHandler(tornado.web.RequestHandler):

    def get(self):
        sd = StatsDisplay(settings["db_dir"])
        table_stats = sd.get_table_stats()

        dates = table_stats["noun_similarity"].keys()
        
        self.write(json.dumps({"dates_available": sorted(dates)}))

class PostProfileHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.ind = Indexer(settings["db_dir"])

    def get_reply_profile(self, cur, noun_md5):
        res= cur.execute("""
            select p.reply_md5, p.reply_cnt, n.noun 
            from post_reply_cnt p
            inner join nouns n 
            on p.reply_md5 = n.noun_md5
            where post_md5 = ?
        """, (noun_md5,)).fetchall()

        profile = []
        for r in res:
            reply_md5, reply_cnt, noun = r
            profile.append( {"noun_md5": str(reply_md5), "noun_text": noun, "reply_cnt": reply_cnt})
        
        profile = sorted(profile, key=lambda x: x["reply_cnt"], reverse=True)

        return profile

    def get_post_cnt(self, cur, noun_md5):
        res = cur.execute("""
            select post_cnt
            from post_cnt
            where post_md5 = ?
        """, (noun_md5, )).fetchone()
        
        return res[0]

    def get_some_tweets(self, cur, noun_md5):
        res = cur.execute("""
            select n.id
            from tweets_nouns n
            inner join tweet_chains t
            on n.id = t.post_id
            where n.noun_md5 = ?
            order by random()
            limit 10
        """, (noun_md5,))

        return map(lambda x: str(x[0]), res)

    def get_common_tweets(self, cur, noun_md5, reply_md5s):
        res = cur.execute("""
            select p_md5, count(*) c from (
                select p_md5, p_id
                from chains_nouns 
                where p_id in (
                    select p_id from chains_nouns
                    where p_md5 =? 
                    group by p_id
                )
                group by p_md5, p_id
            )
            group by p_md5
        """, (noun_md5, )).fetchall()

        repl_common = {}
        for r in res:
            noun, cnt = r
            repl_common[noun] = cnt

        return repl_common


    def get_noun_text(self, cur, noun_md5):
        res = cur.execute("select noun from nouns where noun_md5 = ?", (noun_md5, )).fetchone()
        return res[0]

    def get_most_sim_nouns(self, cur, noun_md5):
        res = cur.execute("""
            select s.post2_md5, s.sim, n.noun
            from noun_similarity s
            inner join nouns n
            on s.post2_md5 = n.noun_md5
            where post1_md5 = ?

            union

            select s.post1_md5, s.sim, n.noun
            from noun_similarity s
            inner join nouns n
            on s.post1_md5 = n.noun_md5
            where post2_md5 = ?
            order by sim
            limit 10
        """, (noun_md5, noun_md5 )).fetchall()
        sim_nouns = map(lambda x: {"noun_md5": x[0], "sim": "%.3f" % x[1], "noun_text": x[2]}, res)
        nouns = map(lambda x: x["noun_md5"], sim_nouns)
        common = self.get_common_tweets(cur, noun_md5, nouns)

        for n in sim_nouns:
            noun = n["noun_md5"]
            n["common_tweet_count"] = common[noun] if noun in common else 0
            
        return sim_nouns


    def get(self):
        noun_md5 = self.get_argument("noun_md5", default=None)
        date = self.get_argument('date', default=None)
        if date is None or date == "" or not re.match("^\d{8}$", date):
            return
        try:
            noun_md5 = int(noun_md5)
        except:
            return

        cur = self.ind.get_db_for_date(date)

        profile = { "noun_md5": noun_md5, 
            "reply_profile": self.get_reply_profile(cur, noun_md5),
            "tweets": self.get_some_tweets(cur, noun_md5),
            "noun_text": self.get_noun_text(cur, noun_md5),
            "post_cnt": self.get_post_cnt(cur, noun_md5),
            "most_similar_nouns": self.get_most_sim_nouns(cur, noun_md5),
        }
                
        self.write(json.dumps(profile))


class ClusterHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.ind = Indexer(settings["db_dir"])

        self.table_stats = StatsDisplay(settings["db_dir"]).get_table_stats()

        dates = self.table_stats["noun_similarity"].keys()
        
        self.available_dates = sorted(dates)

    def get_sims_for_date(self, date):
        cur = self.ind.get_db_for_date(date)
        res = cur.execute("select post1_md5, post2_md5, sim from noun_similarity")

        sim_dict = {}
        while True:
            r = cur.fetchone()
            if r is None:
                break
            p1, p2, sim = r
            if p1 not in sim_dict:
                sim_dict[p1] = {}
            if p2 not in sim_dict:
                sim_dict[p2] = {}
            sim_dict[p1][p2] = sim
            sim_dict[p2][p1] = sim
         
        for p in sim_dict.keys():
            sim_dict[p][p] = 0

        return sim_dict
 
    def get_nouns_for_date(self, date):
        cur = self.ind.get_db_for_date(date)
        return stats.get_nouns(cur)

    def get_clusters_for_date(self, date, k):
        cur = stats.get_cursor(settings["db_dir"] + "/tweets.db") 
        table = "clusters" 
        res = cur.execute("select cluster from %s where cluster_date = ? and k = ?" % (table), ( date, k)).fetchone()


        return res[0]

    def get(self):
        k = self.get_argument('k',default='100')
        date = self.get_argument('date', default=None)
        k = int(k)
        
        if date is None or date == "" or not re.match("^\d{8}$", date):
            date = self.available_dates[-1]

        cl = self.get_clusters_for_date(date, k)

        self.write(cl)

if __name__ == '__main__':
    application = tornado.web.Application([
        (r"/api/cluster", ClusterHandler),
        (r"/api/dates_available", DatesAvailableHandler),
        (r"/api/post_profile", PostProfileHandler),
        #(r"/api/guessr", GuessrHandler),
    ])
    application.listen(8000)
    tornado.ioloop.IOLoop.instance().start()
