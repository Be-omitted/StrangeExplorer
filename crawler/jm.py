# coding=utf-8
# 声明：部分代码来自https://github.com/CYMCOMEING/JMSpider
"""
获取JM指定id漫画的相关信息，暂时仅支持漫画
须使用东亚或东南亚ip(不含大陆ip)

对应SQL的source为：f"JM{id}"，在JMComic.__str__中返回
"""
import shutil
from concurrent.futures import ThreadPoolExecutor
import urllib.request as req
import urllib.error
from playwright.sync_api import sync_playwright
import ssl
import bs4
import re
import hashlib
from hanziconv import HanziConv
from PIL import Image
import os
import os.path
import json

from SQL import TYPE_FILE_IMAGE

ctx = ssl.create_default_context()
ctx.set_ciphers('DEFAULT@SECLEVEL=1')
URL = r"https://18comic.org/"
headers = {
    'accept-language': 'zh-CN,zh;q=0.9',
    'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 '
                  'Safari/537.36',
    'authority': '18comic.vip',
    'origin': 'https://18comic.vip',
    'referer': 'https://18comic.vip',
    'cookie': 'theme=light; sticky=67.159.52.204; _gid=GA1.2.1756399465.1769971325; __PPU_puid=16733628794982262746; cf_clearance=Km3DxbEuJ33vAQBf0R5fyTDNVsDULr4qMq0R1MR55Kk-1770007682-1.2.1.1-uLsV7Xu6orPoZkO89pTzi__8bMHlCTE10AZ4lJOLCLPIAffwsGgIxtTmp9VQIONJUQ2LhengwZDJq.Q4wQzsSp_g191SdZTWuBfBToH9AnIEgvo59cbrviWpbguTZ0ba0UtF3bc.XrUmAeFt_3T4QIK.4LR9EoAX9KUec_wQ0kkd.ZqTESgq1VfwfSv3CbgFEJgcUSYkTjppWRnIDX7OEUIVGQ8MuWRp6ZZgdzB9Tuvx_Uwuvqp11RRFxudgHo01; _clck=icpj7s%5E2%5Eg38%5E0%5E2223; rec_author=%E3%81%9F%E3%81%AC%E3%81%BE; ipcountry=US; AVS=knfkc82jgiephi46393db00jmq; cover=1; guide=1; ipm5=72ef54c2e694a0549dd9827ff03c0361; _ga=GA1.1.1074987445.1769971325; _ga_VW05C6PGN3=GS2.1.s1770007684$o2$g1$t1770008060$j60$l0$h0; _ga_3NP1GJ19M6=GS2.1.s1770007685$o2$g1$t1770008061$j59$l0$h0; _ga_C1BGNGMN6J=GS2.2.s1770007684$o2$g1$t1770008061$j60$l0$h0; _clsk=3r8uxn%5E1770008063057%5E8%5E0%5Ee.clarity.ms%2Fcollect; bnState_2076324=%7B%22impressions%22%3A3%2C%22delayStarted%22%3A0%7D; UGVyc2lzdFN0b3JhZ2U=%7B%22CAIFRQ%22%3A%22ADng1gAAAAAAAAABADnfRwAAAAAAAAABADnVsAAAAAAAAAAEADnVrwAAAAAAAAAB%22%2C%22CAIFRT%22%3A%22ADng1gAAAABpgC9QADnfRwAAAABpgC9QADnVsAAAAABpgC9QADnVrwAAAABpgC9Q%22%7D; bnState_2076328=%7B%22impressions%22%3A4%2C%22delayStarted%22%3A0%7D; bnState_2076322=%7B%22impressions%22%3A4%2C%22delayStarted%22%3A0%7D; bnState_2076320=%7B%22impressions%22%3A4%2C%22delayStarted%22%3A0%7D',
}  # shunt=1 分流1，应该算是比较稳定的一个？
transform_id = 220981
max_pool = 30

def jm_check() -> tuple[bool, int|str]:
    """检查是否可联通"""
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=False, args=["--blink-settings=imagesEnabled=false"])
    pages = browser.new_page()
    pages.goto(URL + "album/" + str(114514), wait_until="domcontentloaded")
    pages.wait_for_timeout(5000)
    daa = pages.content()
    root = bs4.BeautifulSoup(daa, 'html.parser')
    try:
        name = root.find(_tag["homepage_name"][0], class_=_tag["homepage_name"][1]).text.strip()
    except:
        return False, ""
    else:
        return True, f"状态码：200"
def jm_get_id_notes(comics_id: int | str) -> str:
    return f"来自平台：JM\tJM号：{comics_id}"
_tag = {
    "homepage_name": ("h1", "book-name"),
    "homepage_tag": ("a", "phone-tags-tag"),
    "homepage_writer": ("a", "phone-author-tag"),
    "homepage_actor": ("a", "phone-actor-tag"),
    "homepage_works": ("a", "phone-work-tag"),
    "homepage_page": ("span", "pagecount"),
    "homepage_notes": ("h2", "p-b-5"),
}  # 其实内嵌进去反而更方便吧
def read_tag(l : list) -> list[str]: return [HanziConv.toSimplified(i.text.strip()) for i in l]
class JMComic:
    def __init__(self, comics_id: int | str, ):
        self.id = comics_id
        self.error_page_urls = set()  # 表示误下载的不存在的空白页
        while 1:
            p = sync_playwright().start()
            browser = p.chromium.launch(headless=False, args=["--blink-settings=imagesEnabled=false"])
            pages = browser.new_page()
            pages.goto(URL + "album/" + str(comics_id), wait_until="domcontentloaded")
            pages.wait_for_timeout(5000)
            daa = pages.content()
            root = bs4.BeautifulSoup(daa, 'html.parser')
            try:
                self.name = read_tag(root.find_all(_tag["homepage_name"][0], class_=_tag["homepage_name"][1]))[0]
            except:
                p.stop()
            else:
                p.stop()
                break
        self.tag = read_tag(root.find_all(_tag["homepage_tag"][0], class_=_tag["homepage_tag"][1]))
        self.writer = read_tag(root.find_all(_tag["homepage_writer"][0], class_=_tag["homepage_writer"][1]))
        self.actor = read_tag(root.find_all(_tag["homepage_actor"][0], class_=_tag["homepage_actor"][1]))
        self.works = read_tag(root.find_all(_tag["homepage_works"][0], class_=_tag["homepage_works"][1]))
        self.notes = read_tag(root.find_all(_tag["homepage_notes"][0], class_=_tag["homepage_notes"][1]))[0]
        self.notes = re.sub(r"\s+", " ", self.notes)

        self.tags = self.tag + self.writer + self.actor + self.works

        page = read_tag(root.find_all(_tag["homepage_page"][0], class_=_tag["homepage_page"][1]))
        self.page = int(page[0][3:])
        self.chapter = []  # 表示章节名，网页id，页数  # 页数已基本被弃用，仅单章节时作为优化使用
        # 查找章节及其页数
        chapter_f = root.find("ul", class_="btn-toolbar")
        if chapter_f:
            chapter_f = chapter_f.children
            for _c in chapter_f:
                if _c.name == "a":
                    _name = re.sub(r"\s+", " ", read_tag(_c.find("h3"))[0])
                    self.chapter.append([_name, int(_c.get("data-album")), 0])
        else:
            self.chapter.append(["第1话", self.id, self.page])

    def download(self, path: str) -> bool:
        """下载漫画内容至指定目录"""
        path = os.path.join(path, "JMComic#"+str(self.id))
        os.mkdir(path)
        self.__input_message(os.path.join(path, "message.json"))
        pool = ThreadPoolExecutor(max_workers=max_pool)

        download_l = []  # type: list[tuple[int, int, str]]  # 章节uid，页码，章节目录名

        for _c in range(len(self.chapter)):
            _p = os.path.join(path, f"{'%05d'%_c}_{self.chapter[_c][0]}")
            os.mkdir(_p)
            i = 0
            while 1:  # 一次下10页直至找到空白页
                for _ in range(10):
                    download_l.append((self.chapter[_c][1], i+1, _p))
                    i += 1
                r = pool.map(self.__download_one, download_l, chunksize=max_pool)
                for _ in r: pass
                if self.error_page_urls:
                    self.delete_error_page()
                    download_l.clear()
                    break
        return True
    def delete_error_page(self):
        """清除空白页"""
        for i in self.error_page_urls:
            os.remove(i)
        self.error_page_urls.clear()
    @staticmethod
    def update(path: str, uid: str) -> bool:
        """对数据进行更新"""
        if not os.path.isdir(path):
            return False
        cr = JMComic(uid)
        new = os.path.join(path, "new")
        shutil.rmtree(new)
        os.mkdir(new)
        if cr.download(new):
            shutil.copytree(new, path, dirs_exist_ok=True)
            shutil.rmtree(new)
            return True
        else:
            shutil.rmtree(new)
            return False

    def input_message(self, path: str) -> bool:
        """将漫画相关数据导入至目标文件夹"""
        path = os.path.join(path, f"JMComic#{self.id}")
        os.mkdir(path)
        path = os.path.join(path, "message.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"source": f"JMComic#{self.id}", "type": TYPE_FILE_IMAGE, "name": self.name, "tags": self.tags,
                                "tag": self.tag, "writer": self.writer, "actor": self.actor, "works": self.works,
                                "notes": self.notes}, ensure_ascii=False, indent=4))
            return True
    def __input_message(self, path: str) -> bool:
        """将漫画相关数据导入至目标文件"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"source": f"JMComic#{self.id}", "type": TYPE_FILE_IMAGE, "name": self.name, "tags": self.tags,
                                "tag": self.tag, "writer": self.writer, "actor": self.actor, "works": self.works,
                                "notes": self.notes}, ensure_ascii=False, indent=4))
        return True
    def __download_one(self, args):
        _cid, _id, _p = args
        path = os.path.join(_p, ('%05d'%(_id-1))+".webp")
        c = 3
        while c:
            try:
                req.urlretrieve(URL + f"media/photos/{_cid}/" + "%05d" % _id +".webp", path)
            except (urllib.error.HTTPError, urllib.error.URLError):
                c -= 1
            else:
                break
        if not os.path.getsize(str(path)):
            self.error_page_urls.add(str(path))
        else:
            self.img_slice_restore(str(path), str(path[:-5]+'.png'), self.img_get_slices(str(_cid), "%05d"%_id))
            os.remove(path)
    @staticmethod
    def __thread_chapter(l: list):
        _hc = req.Request(url=URL + "photo/" + str(l[1]),
                          headers=headers)
        with req.urlopen(_hc, timeout=60) as data:
            txt = data.read().decode('utf-8')
            root = bs4.BeautifulSoup(txt, 'html.parser')
            l[2] = int(root.find("li", id="phpage").find("span").text[2:])
    # 图像文件处理
    @staticmethod
    def img_slice_restore(img_file: str, out_file: str, slices: int) -> None:
        """根据图片切片数进行还原
        """
        img = Image.open(img_file)

        # 获取图片的宽度和高度
        width, height = img.size

        # 创建一个空白图片，大小与原图一致，背景色为白色
        new_img = Image.new('RGB', (width, height), 'white')

        # 切片高度
        slice_h = int(height / slices)
        slice_other = height % slices
        for i in range(slices):
            # 旧图起始y坐标
            in_img_y = height - slice_h * (i + 1) - slice_other

            # 旧图结束y坐标
            # 新图起始y坐标
            if i == 0:
                in_img_endy = height
                out_img_y = 0
            else:
                in_img_endy = in_img_y + slice_h
                out_img_y = slice_h * i + slice_other

            # crop() 4个参数分别起始坐标和结束坐标
            old_img = img.crop((0, in_img_y, width, in_img_endy))
            new_img.paste(old_img, (0, out_img_y))
        new_img.save(out_file)
    @staticmethod
    def img_get_slices(comic_id: str, page_id: str) -> int:
        """获取图片的切片数
        """
        md5 = hashlib.md5()
        n = ''.join((comic_id, page_id))
        md5.update(n.encode())
        n = int(ord(md5.hexdigest()[-1]))

        # 注释部分是复现js的逻辑，后面已经进行简化
        # if (e > base64.b64decode("MjY4ODUw").decode()) and (e <= base64.b64decode("NDIxOTI1").decode()):
        #     n = n % 10
        # elif e >= str(base64.b64decode("NDIxOTI2")):
        #     n = n % 8

        if (int(comic_id) > 268850) and (int(comic_id) <= 421925):
            n = n % 10
        elif int(comic_id) >= 421926:
            n = n % 8

        return (n+1)*2 if 0 <= n <= 9 else 10

    def __str__(self):
        return f"JM{self.id}"
    __repr__ = __str__
if __name__ == "__main__":
    JMComic(114514).download(r"D:\AAA_practice\python\StrangeExplorer\test\save\scratch")
