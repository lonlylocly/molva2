#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import os
import logging, logging.config
import json

import stats
from Indexer import Indexer
from util import digest
import util

logging.config.fileConfig("logging.conf")

settings = {} 
try:
    settings = json.load(open('global-settings.json', 'r'))
except Exception as e:
    logging.warn(e)

POST_MIN_FREQ = settings["post_min_freq"] if "post_min_freq" in settings else 10

DB_DIR = settings["db_dir"] if "db_dir" in settings else os.environ["MOLVA_DIR"]

BLOCKED_NOUNS_LIST = u"\n".join(list(u"абвгдеёжзиклмнопрстуфхцчшщыьъэюя"))

BLOCKED_NOUNS = ",".join(map( lambda x: str(digest(x)), BLOCKED_NOUNS_LIST.split("\n")))

NOUNS_LIMIT = 2000


def save_sims(cur, sims):
    cur.execute("begin transaction")

    cur.executemany("replace into noun_sim_new values (?, ?, ?)", sims)

    cur.execute("commit")

def fill_sims(cur, profiles_dict, nouns, tweets_nouns):
    logging.info("Start filling sims iteration")
    posts = profiles_dict.keys()

    cnt = 0
    long_cnt = 1
    sims = []
    for i in xrange(0, len(posts)):
        post1 = posts[i]
        for j in xrange(0, len(posts)):
            post2 = posts[j]
            if post1 <= post2:
                continue
            p_compare = profiles_dict[post1].compare_with(profiles_dict[post2])
            sims.append((post1, post2, p_compare.sim))

            cnt += 1

            if len(sims) > 10000:
                save_sims(cur, sims)
                sims = []
            if cnt > long_cnt * 10000:
                long_cnt += 1
                logging.info("Another 10k seen")
     
    save_sims(cur, sims)

def update_sims(cur):
    cur.execute("begin transaction")

    cur.execute("drop table if exists noun_sim_old")
    cur.execute("alter table noun_similarity rename to noun_sim_old")
    cur.execute("alter table noun_sim_new rename to noun_similarity")
    cur.execute("drop table noun_sim_old")

    cur.execute("commit")

def main():
    logging.info("start")
    parser = util.get_dates_range_parser()
    parser.add_argument("-c", "--clear", action="store_true")
    parser.add_argument("-p", "--profiles-table", default="post_reply_cnt")
    parser.add_argument("-o", "--out-file")
    args = parser.parse_args()

    ind = Indexer(DB_DIR)
    cur = stats.get_main_cursor(DB_DIR)
            
    profiles_dict = stats.setup_noun_profiles(cur, {}, {}, 
        post_min_freq = POST_MIN_FREQ, blocked_nouns = BLOCKED_NOUNS, nouns_limit = NOUNS_LIMIT, profiles_table = args.profiles_table 
    )

    logging.info("profiles len %s" % len(profiles_dict))
    profiles_dump = {}
    for p in profiles_dict:
        profiles_dump[p] = profiles_dict[p].replys

    json.dump(profiles_dump, open(args.out_file, 'w')) 

if __name__ == '__main__':
    main()


