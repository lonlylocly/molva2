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
from datetime import datetime, timedelta

import KMeanCluster
import stats
from Indexer import Indexer
import util

logging.config.fileConfig("logging.conf")

settings = json.load(open('global-settings.json', 'r'))

class ClusterHandler(tornado.web.RequestHandler):

    def get_clusters(self, skip, before, date):
        cur = stats.get_cursor(settings["db_dir"] + "/tweets_display.db") 
        if date is not None:
            cur.execute("""
                select cluster 
                from clusters 
                where cluster_date = '%(date)s'
            """  % ({'date': date}))
        elif before is not None:
            cur.execute("""
                select cluster 
                from clusters 
                where cluster_date < '%(before)s'
                order by cluster_date desc 
                limit 1 
            """ % ({'before': before}))
        else:
            cur.execute("""
                select cluster 
                from clusters 
                order by cluster_date desc 
                limit 1 
                offset %s
            """ % (skip))
        res = cur.fetchone()[0] 

        return res

    def parse_date(self, mydate):
        if mydate is None or mydate == "":
            return None
        try:
            mydate = mydate.replace("-","").replace(" ","").replace(":","") 

            unixtime = datetime.strptime(mydate, "%Y%m%d%H%M%S").strftime("%s")
            mydate_dt = datetime.utcfromtimestamp(int(unixtime))
            mydate = mydate_dt.strftime("%Y%m%d%H%M%S")
            
            return mydate
        except Exception as e:
            logging.info(e)
            return None

    def get(self):
        skip = self.get_argument("skip", default=0)
        before = self.parse_date(self.get_argument("before", default=None))
        date = self.parse_date(self.get_argument("date", default=None))
        try:
            skip = int(skip)
        except:
            skip = 0

        logging.info("Before %s (UTC)" % before)
        logging.info("Date %s (UTC)" % before)

        cl = self.get_clusters(skip, before, date)

        self.write(cl)

class RelevantHandler(tornado.web.RequestHandler):

    def get_relevant(self, date):
        cur = stats.get_cursor(settings["db_dir"] + "/tweets_relevant.db") 
        if date is not None:
            cur.execute("""
                select relevant 
                from relevant
                where cluster_date = '%(date)s'
            """  % ({'date': date}))

        res = cur.fetchone()[0] 

        return res

    def parse_date(self, mydate):
        if mydate is None or mydate == "":
            return None
        try:
            mydate = mydate.replace("-","").replace(" ","").replace(":","") 

            unixtime = datetime.strptime(mydate, "%Y%m%d%H%M%S").strftime("%s")
            mydate_dt = datetime.utcfromtimestamp(int(unixtime))
            mydate = mydate_dt.strftime("%Y%m%d%H%M%S")
            
            return mydate
        except Exception as e:
            logging.info(e)
            return None

    def get(self):
        date = self.parse_date(self.get_argument("date", default=None))
        
        logging.info("Date %s (UTC)" % date)
        logging.info(str(self.cookies))

        r = self.get_relevant(date)

        self.write(r)

class TrendHandler(tornado.web.RequestHandler):

    @util.time_logger
    def get_word_time_cnt(self, word_md5, time1, time2):
        logging.info("Get word time cnt: %s, %s, %s" % (word_md5, time1, time2))
        utc_now = datetime.utcnow()
        res = []
        default_left_time_bound = (utc_now - timedelta(3)).strftime("%Y%m%d%H%M%S")[:11]
        time = ""
        if time1 is not None:
            time += " and tenminute >= " + time1
        else:
            time += " and tenminute >= " + default_left_time_bound
        if time2 is not None:
            time += " and tenminute < " + time2

        where = "word_md5 = %s" % word_md5
        if word_md5 == util.digest('0'):
            where = "1"

        for day in [3, 2, 1, 0]:
            date = (utc_now - timedelta(day)).strftime("%Y%m%d")
            cur = stats.get_cursor("%s/words_%s.db" % (settings["db_dir"], date))
            stats.create_given_tables(cur, ["word_time_cnt"])
            cur.execute("""
                select word_md5, substr(tenminute, 1, 10) as hour, sum(cnt) 
                from word_time_cnt
                where %(where)s 
                %(time)s
                group by hour
            """ % {"where": where, "time": time})
            res += cur.fetchall()
        return res

    def parse_times(self, time1, time2):
        try:
            if time1 is not None:
                time1 = "{:0<11d}".format(int(time1))
            if time2 is not None:
                time2 = "{:0<11d}".format(int(time2))
            if time1 is not None and time2 is not None and time1 > time2:
                time1, time2 = time2, time1
        except Exception as e:
            logging.error(e)
            time1 = None
            time2 = None

        return (time1, time2)

    def get(self):
        try:
            word = self.get_argument("word", default=None)
            time1 = self.get_argument("time1", default=None)
            time2 = self.get_argument("time2", default=None)
            logging.info("Request: %s, %s, %s" % (word, time1, time2))

            if word is None:
                return
            
            time1, time2 = self.parse_times(time1, time2)

            word_md5 = util.digest(word.strip())       
            logging.info("Get time series for '%s' (%s)" % (word, word_md5))
           
            res = self.get_word_time_cnt(word_md5, time1, time2)

            res = sorted(res, key=lambda x: x[1])
            res = map(lambda x: {"hour": x[1], "count": x[2]}, res)
            #mov_av = [0]
            #for i in range(1, len(res) -1):
            #    ma = float(res[i-1]["count"] + res[i]["count"] + res[i+1]["count"]) / 3
            #    mov_av.append(ma)
            #mov_av.append(0)

            self.write(json.dumps({"word": word_md5, "dataSeries": res}))
        except Exception as e:
            logging.error(e)
            raise e
   
class QualityMarkHandler(tornado.web.RequestHandler):

    def post(self):
        req_data = None
        try:
            req_data = json.loads(self.request.body)

            if req_data is not None:
                cur = stats.get_cursor(settings["db_dir"] + "/quality_marks.db") 
                stats.create_given_tables(cur, ["quality_marks"])
                username = ""
                if "username" in req_data and req_data["username"] is not None:
                    username = req_data["username"]
                update_time = ""
                if "update_time" in req_data and req_data["update_time"] is not None:
                    update_time = req_data["update_time"]
                    update_time = int(re.sub('[-\s:]','', update_time))
                cur.execute("""
                    insert into quality_marks 
                    (update_time, username, marks) 
                    values (?, ?, ?)
                """, (update_time, username, json.dumps(req_data["marks"])))

        except Exception as e:
            logging.error(e)
            raise(e)

        self.write("")

if __name__ == '__main__':
    application = tornado.web.Application([
        (r"/api/cluster", ClusterHandler),
        (r"/api/relevant", RelevantHandler),
        (r"/api/trend", TrendHandler),
        (r"/api/mark_topic", QualityMarkHandler)
    ])
    application.listen(8000)
    tornado.ioloop.IOLoop.instance().start()
