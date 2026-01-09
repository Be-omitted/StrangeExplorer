# coding=utf-8
__version__ = "1.1"  # bika你怎么突然大改了啊
"""
获取BiKa指定id漫画的相关信息，暂时仅支持漫画
存在异步问题，每个BiKaComic需要独立线程
在较差的网络环境下可能获取失败
须使用非大陆ip

对应SQL的source为：f"BiKa{id}"，在BiKaComic.__str__中返回
"""
import playwright
from playwright.sync_api import sync_playwright
import bs4
from hanziconv import HanziConv
import re
import os, os.path
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
import json
from os.path import join
import ssl

from SQL import TYPE_FILE_IMAGE
ssl._create_default_https_context = ssl._create_unverified_context
URL = "https://manhuabika.com/"
# headers = {
#     "accept": r"text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
#     "accept-encoding": "gzip, deflate, br, zstd",
#     "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
#     "priority": "u=0, i",
#     "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
#     "sec-ch-ua-mobile": "?0",
#     "sec-ch-ua-platform": '"Windows"',
#     "sec-fetch-dest": "document",
#     "sec-fetch-mode": "navigate",
#     "sec-fetch-site": "same-origin",
#     "sec-fetch-user": "?1",
#     "if-modified-since": "Thu, 02 Oct 2024 01:19:32 GMT",
#     "upgrade-insecure-requests": "1",
#     "Referer": "https://manhuabika.com/",
#     "Origin": "https://manhuabika.com",
#     "cookie": "_ga=GA1.1.502291155.1759415000; _ga_CYD4PLDZG2=GS2.1.s1759415000$o1$g1$t1759415131$j60$l0$h0"
# }

_email = "OMITT"
_password = "OMITT123456"

def bika_plogin() -> tuple[playwright.sync_api.Playwright, playwright.sync_api.Page]:
        p = sync_playwright().start()
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL)

        cookie_selector = "svg[xmlns='http://www.w3.org/2000/svg']"
        page.wait_for_selector(cookie_selector, state="visible", timeout=10000)
        page.click(cookie_selector)
        cookie_selector = "div.speedtest-domain-speed"
        page.wait_for_selector(cookie_selector, state="visible", timeout=10000)
        page.click(cookie_selector)

        page.wait_for_selector("input[id='username']", state="visible", timeout=10000)
        page.fill("input[id='username']", _email)
        page.fill("input[id='password']", _password)
        page.click("button[type='submit']")

        page.wait_for_url(URL)
        page.wait_for_timeout(5000)
        return p, page

def bika_check() -> tuple[bool, int|str]:
    try:
        p, page = bika_plogin()
        status_code = page.evaluate("() => document.readyState")
        page.close()
        p.stop()
        if status_code in ("complete", "interactive"):
            return True, f"{status_code}"
        else:
            return False, f"{status_code}"
    except Exception as e:
        return False, str(e)

def bika_get_id_notes(cid: int | str) -> str:
    return f"来自平台：BiKa\tBiKa号：{cid}"

def read_tag(l : list) -> list[str]: return [HanziConv.toSimplified(re.sub(r'\u00a0+', ' ', i.text.strip())) for i in l]
class BiKaComic:
    def __init__(self, cid: str) -> None:  # 为什么是叫cid? 因为网页原标签就是cid
        self.cid = cid
        try:
            p, page = bika_plogin()
        except TypeError:
            p, page = bika_plogin()
        page.goto(URL+f"comic/{self.cid}")
        page.wait_for_load_state("networkidle")
        html = page.content()

        root = bs4.BeautifulSoup(html, 'html.parser')

        self.name = read_tag(root.find_all("h1", class_="comic-title"))[0]
        self.author = read_tag(root.find_all("span", class_="comic-hero-author"))[0]
        self.notes = read_tag(root.find_all("p", class_="description-text"))[0]
        _class = read_tag(root.find("div", class_="tags-container").find_all("span", recursive=False))
        self.tag = [i[1:] if i[0] == "#" else i for i in _class]  # 一点修改后的遗留
        self.tags = self.tag.copy()
        self.tags.append(self.author)

        self.chapter = int(read_tag(root.find_all("span", class_="comic-tab-badge"))[0])
        self.p = p
        self.page = page
        self.data = []

    def download(self, path: str, is_hard: bool = True) -> bool:
        """
        下载漫画内容至指定目录\n
        is_hard: 如果文件存在，是否覆盖，一般在更新操作时禁用
        """
        path = os.path.join(path, f"BIKAComic#{self.cid}")
        if not os.path.isdir(path):
            os.mkdir(path)
        self.__input_message(join(path, "message.json"))

        for i in range(self.chapter):
            _path = os.path.join(path, "%05d"%i)
            if not os.path.isdir(_path):
                os.mkdir(_path)
            self.page.goto(URL+f"comic/reader/{self.cid}/{i+1}")
            self.page.wait_for_load_state("networkidle")
            if not i:  # 首次切到高清与单图
                self.page.click("button[title='阅读设置']")
                self.page.wait_for_selector("div.single-tab-navigation", state="visible", timeout=10000)
                self.page.wait_for_timeout(1000)
                self.page.click("span:has-text('显示')")
                self.page.wait_for_selector("button.single-quality-btn:has-text('原图')", state="visible", timeout=10000)
                self.page.wait_for_timeout(1000)
                self.page.click("button.single-quality-btn:has-text('原图')")
                self.page.click("span:has-text('阅读器')")
                self.page.wait_for_timeout(1000)
                self.page.click("span:has-text('单页模式')")
                self.page.wait_for_timeout(1000)
                self.page.goto(URL+f"comic/reader/{self.cid}/{i+1}")
            self.page.wait_for_timeout(2000)
            page_text = self.page.locator("span.page-text").text_content()
            img_max = int(page_text.split("/")[1])

            ad_num = 0
            ad_count = 0
            for img_this in range(img_max-1):
                img_this += 1
                ad_count += 1
                if ad_count == 21:  # 广告每20张插1张
                    ad_num += 1
                    ad_count = 0
                    self.page.click("button[title='下一页']")
                    self.page.wait_for_timeout(200)
                    continue
                img_src = self.page.locator("img[alt='Page "+str(img_this)+"']").get_attribute("src")
                self.data.append((img_src, os.path.join(_path, "%05d" % (img_this-ad_num-1) + os.path.splitext(img_src)[1]), is_hard))
                self.page.click("button[title='下一页']")
                self.page.wait_for_timeout(200)
            img_src = self.page.locator("img[alt='Page " + str(img_max) + "']").get_attribute("src")
            self.data.append((img_src, os.path.join(_path, "%05d" % (img_max-ad_num-1) + os.path.splitext(img_src)[1]), is_hard))

            # img = [i["data-src"] for i in root.find("div", id="chapter-images-id").find_all("img", recursive=False)]
            # imgs.append(img)
        # if not imgs[0]:  # 有时首个获取失败，重新获取
        #     _path = os.path.join(path, "%05d_"%0+self.chapter[0])
        #     self.page.goto(URL+f"pchapter/?cid={self.cid}{end0}{1}{end1}")
        #     self.page.wait_for_load_state("networkidle")
        #     self.page.wait_for_timeout(2000)
        #     html = self.page.content()
        #     root = bs4.BeautifulSoup(html, 'html.parser')
        #     img = [i["data-src"] for i in root.find("div", id="chapter-images-id").find_all("img", recursive=False)]
        #     imgs[0] = img
        #
        # p_data = []
        # for i in range(len(imgs)):
        #     _path = os.path.join(path, "%05d_" % i + self.chapter[i])
        #     for _i in range(len(imgs[i])):
        #         __path = os.path.join(_path, "%05d" % _i + os.path.splitext(imgs[i][_i])[1])
        #         if not is_hard and os.path.isfile(__path):
        #             continue
        #         p_data.append((imgs[i][_i], __path))
        for i in range(0, len(self.data), 10):
            with ThreadPoolExecutor(max_workers=10) as p:
                _p = p.map(self.__one_download, self.data[i:i+10])
                for _ in _p: pass
        # for _url, __path in self.data:
        #     if not is_hard and os.path.isfile(__path):
        #         continue
        #     def handle_response(response):
        #         if response.url == _url and response.status == 200:
        #             self.page.wait_for_load_state("networkidle")
        #             self.page.wait_for_timeout(1000)
        #             image_data = response.body()
        #             with open(__path, "wb") as f:
        #                 f.write(image_data)
        #     self.page.on("response", handle_response)
        #     self.page.goto(_url)
        return True

    def input_message(self, path: str) -> bool:
        """将漫画相关数据导入至目标文件夹"""
        path = join(path, f"BIKAComic#{self.cid}")
        os.mkdir(path)
        path = join(path, "message.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"source": f"BIKAComic#{self.cid}", "type": TYPE_FILE_IMAGE, "name": self.name, "tags": self.tags,
                                "tag": self.tag, "writer": self.author,
                                "notes": self.notes}, ensure_ascii=False, indent=4))
            return True
    def __input_message(self, path: str) -> bool:
        """将漫画相关数据导入至目标文件"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"source": f"BIKAComic#{self.cid}", "type": TYPE_FILE_IMAGE, "name": self.name, "tags": self.tags,
                                "tag": self.tag, "writer": self.author,
                                "notes": self.notes}, ensure_ascii=False, indent=4))
            return True
    def __one_download(self, arg: tuple[str, str, bool]):
        _url, __path, _is = arg
        try:
            if not _is and os.path.isfile(__path):
                return
            urllib.request.urlretrieve(_url, __path)
        except urllib.error.HTTPError:
            pass

    def __str__(self) -> str:
        return f"BIKA{self.cid}"
    __repr__ = __str__

    def __del__(self):
        try:
            if self.page:
                self.page.close()
        except:
            pass
        try:
            if self.p:
                self.p.stop()
        except:
            pass

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=10) as __p:
        ___p = __p.map(lambda x: BiKaComic(x).download(r"D:\AAA_practice\python\StrangeExplorer\test\save\scratch"), ["694fff379b2dc87f8b55cba5"])
        for _ in ___p: pass
