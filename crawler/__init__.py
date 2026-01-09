# coding=utf-8
"""
为该程序提供下载支持的简单爬虫库

对于信息文件(json)，确保拥有以下内容：
    source: 表示来源网站内部的标识
    type: 类型, int(参考SQL.py)
    name: 名称
    tags: 标签列表
    notes: 备注
该文件存放在主目录下，文件名固定为"message.json"
"""
import argparse
import json
from os.path import join

from crawler.jm import JMComic, jm_check, jm_get_id_notes
from crawler.bika import BiKaComic, bika_check, bika_get_id_notes
__version__ = "1.0"
__all__ = []

def get_basic_message(path: str) -> dict:
    """
    获取漫画基本信息
    :param path: 漫画目录
    :return: 漫画基本信息
    """
    with open(join(path, "message.json"), "r", encoding="utf-8") as f:
        return json.load(f)

if __name__ == "__main__":
    # from concurrent.futures import ThreadPoolExecutor
    # check = ((jm_check, "jm"),
    #          (bika_check, "bika"),
    #          )
    #
    # with ThreadPoolExecutor(max_workers=10) as pool:
    #     nc = []
    #     def check_comic(_d):
    #         def _check():
    #             print(f"访问测试：{_d[1]}")
    #             print(f"{_d[1]}访问结束：", *_d[0](), sep=" ")
    #         return _check
    #     for _d in check:
    #         nc.append(check_comic(_d))
    #     p = pool.map(lambda x: x(), nc)
    #     for _ in p: pass
    import sys
    from os.path import isdir

    crawler_type = ("JMComic", "BikaComic")

    parser = argparse.ArgumentParser(description="StrangeExplorer附带的爬虫包")
    parser.add_argument("--source", type=str, dest="source", choices=crawler_type, required=True,
                        help=f"数据来源,{crawler_type}")
    parser.add_argument("--key", "-k", type=str, dest="key",
                        help="在该网站的标识符")
    parser.add_argument("--save", type=str, dest="save",
                        help="储存至何位置")
    parser.add_argument("--check", action="store_true", dest="check",
                        help="测试模式")
    parser.add_argument("--message", "-m", action="store_true", dest="message",
                        help="仅获取信息")
    parser.add_argument("--update", "-u", type=str, dest="update",
                        help="更新指定目录")

    args = parser.parse_args()
    try:
        if args.source == "JMComic":
            if args.check:
                sys.exit(not jm_check()[0])
            elif args.key and args.save and isdir(args.save):
                data = JMComic(args.key)
                if args.message:
                    data.input_message(args.save)
                elif args.update and isdir(args.update):
                    data.update(args.update, args.key)
                else:
                    data.download(args.save)
            else:
                sys.exit(1)
        elif args.source == "BikaComic":
            if args.check:
                sys.exit(not bika_check()[0])
            elif args.key and args.save and isdir(args.save):
                data = BiKaComic(args.key)
                if args.message:
                    data.input_message(args.save)
                elif args.update and isdir(args.update):
                    data.download(args.update, is_hard=False)
                else:
                    data.download(args.save)
            else:
                sys.exit(1)
    except Exception as e:
        sys.exit(1)
    else:
        sys.exit(0)
