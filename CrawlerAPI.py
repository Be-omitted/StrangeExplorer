# coding=utf-8
"""
此程序的爬虫接口\n
爬虫插件将被拷贝至[BaseUrl]下\n
对于一个适配的爬虫插件，需满足：\n
    爬虫程序所在文件夹中存在文件config.json:\n
        字典结构\n
        name: str，名称，例："JM-漫画"\n
        notes: str，对爬虫实际功能的描述，例："提供JM号以提供JM漫画的下载，需要非大陆IP"\n
        mark: str，信息文件（见下文）中的source必须以此为开头，以"#"结尾，例："JM-漫画#"\n

        init: str，可选的，初始化指令，将在程序开始时自动调用一次，返回非零值表示初始化失败，例："[BaseUrl]\\JMCrawler\\init.exe True"\n
        check：str，可选的，检查连接运行是否正常，返回非零值表示连接异常，例："[BaseUrl]\\JMCrawler\\crawler.exe --check"\n
        download_message: str，表示获取资源相关信息（见下文信息文件），需将数据存放至"[DataUrl]\\"中以资源名命名的文件夹，返回非零值表示表示失败，
                        例："[BaseUrl]\\JMCrawler\\crawler.exe [KEY] -m -w [DataUrl]\\"\n
        download_data：str，表示获取资源，需将数据存放至"[DataUrl]\\"中以资源名命名的文件夹，并同步保存与download_message相同文件，返回非零值表示表示失败，
                        例："[BaseUrl]\\JMCrawler\\crawler.exe [KEY] --download -w [DataUrl]\\"\n
        update_data: str，表示对已有资源进行更新，须将数据存放至"[OldUrl]"中（[OldUrl]将原样保留download_data获取的文件结构，message.json的source项不会更改），返回非零值表示表示失败，
                        例："[BaseUrl]\\JMCrawler\\crawler.exe [KEY] --download --save [OldUrl]"\n
    预定义的替换文本：\n
        [BaseUrl]：爬虫文件夹的父目录地址\n
        [DataUrl]：临时资源存储地址\n
        [KEY]：用户输入的指向爬取目标的关键字，只在download_message，download_data与update_data启用\n
        [OldUrl]：预更新的旧文件地址，只在update_data启用\n
    对于信息文件(json)，确保拥有以下内容：\n
        source: 表示来源网站内部的标识，须以上述mark开头，str，例："JM-漫画#350234"\n
        type: 类型，int(参考SQL.py)\n
        name: 名称，str\n
        tags: 标签列表，list\n
        notes: 备注，str\n
    该文件存放在主目录下，文件名固定为"message.json"\n
"""
import subprocess
import json
import shutil
import os.path

class CrawlerRule:
    """
    对Crawler输出与指令文本等进行修饰与限制\n
    replaceRule:\n
        对输入与指令文本都应用，将sign替换为value，定义重复的sign将替换\n
        sign: 以"[Key]"为模板，key为自定义的文本\n
        注意：禁止在value中包含sign（包括非对应此value的key），这是未定义的\n
        注意："[KEY][OldUrl]"是被预先占用的，表示用户输入的指向爬取目标的关键字，只在Crawler.message_data与Crawler.download_data启用
    """

    def __init__(self):
        self.replaceRule = {}  # type:dict[str: str]

    def update_replaceRule(self, sign: str, value: str) -> bool:
        """
        更新replaceRule\n
        不满足要求将返回False并终止
        """
        if (not sign) or sign in value \
                or sign[0] != '[' or sign[-1] != ']' or sign in ("[KEY]", "[OldUrl]") \
                or sign in "".join(self.replaceRule.values()):
            return False
        for _sign in self.replaceRule.keys():
            if _sign in value:
                return False
        self.replaceRule[sign] = value
        return True

    def __call__(self, source: str, key: str | None = None, old: str | None = None) -> str:
        # 标识替换
        for _sign, _v in self.replaceRule.items():
            source = source.replace(_sign, _v, -1)
        if key:
            source = source.replace("[KEY]", key, -1)
        if old:
            source = source.replace("[OldUrl]", old, -1)
        source = source.replace("\\", "/", -1)
        return source
class Crawler:
    """
    供此程序识别与使用的爬虫接口
    """
    def __init__(self, rule: CrawlerRule,
                 name: str, notes: str, mark: str,
                 download_message: str, download_data: str, update_data: str,
                 init: str = "", check: str = "", ):
        self.rule = rule
        self.name = name
        self.notes = notes
        self.mark = mark

        self.init = init
        self.check = check
        self.download_message = download_message
        self.download_data = download_data
        self.update_data = update_data

    def use_init(self) -> bool:
        if not self.init:
            return True
        go = self.rule(self.init)
        try:
            return not subprocess.run(go).returncode
        except FileNotFoundError:
            return False
    def use_check(self) -> bool:
        if not self.check:
            return False
        go = self.rule(self.check)
        try:
            return not subprocess.run(go).returncode
        except FileNotFoundError:
            return False
    def use_download_message(self, key: str) -> bool:
        if not self.download_message:
            return False
        go = self.rule(self.download_message, key=key)
        try:
            return not subprocess.run(go).returncode
        except FileNotFoundError:
            return False
    def use_download_data(self, key: str) -> bool:
        if not self.download_data:
            return False
        go = self.rule(self.download_data, key=key)
        try:
            return not subprocess.run(go).returncode
        except FileNotFoundError:
            return False
    @staticmethod
    def use_update_data(cr_l: list['Crawler'], old: str) -> bool:
        if not cr_l:
            return False
        dir_l = os.listdir(old)
        if (not dir_l) or (not "message.json" in dir_l):
            return False
        with open(os.path.join(old, "message.json"), "r", encoding="utf-8") as f:
            data_d = json.loads(f.read())  # type: dict
        if not isinstance(data_d, dict) or not "source" in data_d.keys():
            return False
        s_mark = data_d["source"]  # type: str
        try:
            s_mark = s_mark[:s_mark.index("#")+1]
            key = s_mark[s_mark.index("#")+1:]
        except ValueError:
            return False
        for cr in cr_l:
            if cr.mark == s_mark:
                go = cr.rule(cr.update_data, old=old, key=key)
                try:
                    return not subprocess.run(go).returncode
                except FileNotFoundError:
                    return False
        return False


    def get_notes(self) -> str: return self.notes

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<Crawler-{self.name} --> {self.notes}>"

def read_file_crawler(path: str, rule: CrawlerRule) -> list[Crawler]:
    """从配置文件中读取数据"""
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        l = json.loads(f.read())
    cl = []
    for _d in l["crawler"]:
        if {"name", "notes", "mark", "init", "check", "download_message", "download_data", "update_data"}.issubset(set(_d)):
            cl.append(Crawler(rule, name=_d["name"], notes=_d["notes"], mark=_d["mark"],
                              download_message=_d["download_message"], download_data=_d["download_data"],
                              update_data=_d["update_data"], init=_d["init"], check=_d["check"]))
    return cl

def init_crawler(rule: CrawlerRule, src: str, message_path: str) -> tuple[bool, dict]:
    """导入新爬虫"""
    if not os.path.isdir(src):
        return False, {}
    dst = os.path.join(rule.replaceRule["[BaseUrl]"], os.path.basename(os.path.normpath(src)))
    shutil.copytree(src=src, dst=dst, dirs_exist_ok=True)
    new_message = os.path.join(dst, "message.json")
    with open(new_message, "r", encoding="utf-8") as f:
        new_message = json.loads(f.read())
    with open(message_path, "r", encoding="utf-8") as f:
        message = json.loads(f.read())
    message["crawler"].extend(new_message)
    with open(message_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(message, ensure_ascii=False, indent=4))
    return True, new_message
