# coding=utf-8
import sys
import typing
import tk
from types import SimpleNamespace
from hanziconv import HanziConv
from PIL import Image, ImageTk
import json
import ctypes
from concurrent.futures import ThreadPoolExecutor
import os, os.path
import webbrowser
import SQL
import subprocess
import CrawlerAPI

NAME = "StrangeExplorer"
__version__ = "1.0"
HEAD = f"{NAME}{__version__}"
THIS_PATH = os.getcwd()
ICO_PATH = os.path.join(THIS_PATH, "common\\m_icon.ico")

USER32 = ctypes.windll.user32
SCREEN_W = USER32.GetSystemMetrics(0)
SCREEN_H = USER32.GetSystemMetrics(1)

DEFAULT_SAVE_JSON = {"history_path": "", "crawler": []}

def init_style() -> tk.Style:
    """样式初始化"""
    # 色表
    blue0 = "#E0EEEE"
    pink0 = "#FFF0F5"
    frame0 = "#FFFAF0"
    frame1 = "#EEEEE0"
    # 样式
    style = tk.Style()
    # 上级界面
    style.configure("Main.TNotebook",
                         background="lightgray",
                         height=10)
    style.configure("Main.TNotebook.Tab",
                         width=10, anchor="center")
    style.layout("Main.TNotebook.Tab", [
        ('Notebook.tab', {'sticky': 'nswe', 'children': [
            ('Notebook.padding', {'side': 'top', 'sticky': 'nswe', 'children': [
                ('Notebook.label', {'side': 'top', 'sticky': ''})
            ]})
        ]})
    ])
    style.map("Main.TNotebook.Tab", foreground=[
        ("selected", "pink"),
        ("active", "skyblue")
    ])

    style.configure("MainBase.TFrame", background=frame1)
    style.configure("MainBase.TLabel", background=frame1)
    style.configure("MainValues.TFrame", background=pink0)
    style.configure("MainBase.TRadiobutton", background=frame1)

    # 通用
    style.configure("INFO.TLabel", background="#BEBEBE", anchor="center")
    style.configure("Name.TLabel", background=pink0, anchor="nw")
    style.configure("Notes.TLabel", background=blue0, foreground="#555555", justify="left", anchor="nw")
    style.configure("TagFrame.TFrame", background=frame0)
    style.configure("TagMessageFrame.TFrame", background=pink0)
    # Listbox相关
    style.configure("ListBox.TFrame", background=frame0)
    style.configure("ListBoxFileSize.TLabel", background=frame0, anchor="w")
    style.configure("ListBoxFileTag.TFrame", background=blue0)
    style.configure("ListBoxF.TSeparator", background='black')
    style.configure("ListBoxName.TEntry", background=pink0, justify="center", relief="flat")
    style.configure("ListBoxName.TLabel", background=pink0)
    style.configure("ListBoxType.TLabel", background=pink0)
    style.configure("ListBoxNotes.TLabel", background=blue0, foreground="#555555", justify="left")
    style.configure("ListBoxXQ.TButton")
    # TagBox相关
    style.configure("TagBox.TButton")
    style.configure("TagBoxHead.TLabel", background=frame0, foreground="#555555")
    return style
def get_file_cover(url_dir: str|typing.LiteralString, _type: int, size: tuple[int, int]) -> ImageTk.PhotoImage:
    """将url_dir以_type为类型查询大小为size的封面"""
    is_cover = False
    url = ""
    url_dir = url_dir.replace("\\", "/", -1)
    try:
        if _type == SQL.TYPE_FILE_IMAGE:
            is_cover, url = SQL.get_image_cover(url_dir)
        elif _type == SQL.TYPE_FILE_TEXT:
            is_cover, url = SQL.get_text_cover(url_dir)
        elif _type == SQL.TYPE_FILE_GAME:
            is_cover, url = SQL.get_game_cover(url_dir)
        elif _type == SQL.TYPE_FILE_VIDEO:
            is_cover, url = SQL.get_video_cover(url_dir)
        if is_cover:
            image = Image.open(url)
        else:
            image = Image.open(r".\common\image\no_cover.png")

    except (FileNotFoundError, OSError):
        image = Image.open(r".\common\image\no_cover.png")

    image = image.resize(size, Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(image)
def get_file_size(url_dir: str|typing.LiteralString, _type: int) -> tuple[int, int]:
    """将url_dir以_type为类型查询（文件数, 文件夹数）"""
    if _type == SQL.TYPE_FILE_IMAGE:
        return SQL.get_image_size(url_dir)
    else:
        return 0, 0

def win_tag(fwin: tk.Tk | tk.Toplevel, ex: SQL.Explorer, name: str) -> tk.Toplevel:
    """tag的细节描述界面"""
    win = tk.Toplevel(fwin)
    win.geometry(f"300x200+{fwin.winfo_x()}+{fwin.winfo_y()}")
    win.wm_iconbitmap(ICO_PATH)
    win.title(HEAD+f"--tag to {name}")

    cur = ex.conn.cursor()
    tag_data = cur.execute("SELECT NOTES, IN0GROUP, TYPE FROM TAG WHERE NAME == ?;", (name, )).fetchall()

    name_l = tk.Label(win, text=f"名称： {name}\t类型： {SQL.NAME_TYPE[tag_data[0][2]]}", style="Name.TLabel")
    note_l = tk.Label(win, text=tag_data[0][0], wraplength=win.winfo_width()-10, style="Notes.TLabel", anchor="nw")
    tag_in_f = tk.Frame(win, style="TagFrame.TFrame")

    tag_in = TagBox(win, tag_in_f, "位于以下tag group中：", True)
    def win_t(func: typing.Callable, _n):
        def win__t():
            func(fwin, ex, _n)
        return win__t
    for n in SQL.to_r_tag(tag_data[0][1]):
        tag_in.add_tag(n, win_t(win_tag0group, n))

    name_l.grid(row=0, column=0, sticky="nsew")
    note_l.grid(row=1, column=0, sticky="nsew")
    tag_in_f.grid(row=2, column=0, sticky="nsew")
    win.columnconfigure(0, weight=1)
    win.rowconfigure(1, weight=1)
    win.rowconfigure(2, weight=2)

    win.bind("<Enter>", lambda e: note_l.config(wraplength=win.winfo_width()-10))
    del tag_data
    tag_in.fresh()
    cur.close()
    win.mainloop()
    return win
def win_tag0group(fwin: tk.Tk | tk.Toplevel, ex: SQL.Explorer, name: str) -> tk.Toplevel:
    """tag group的细节描述界面"""
    win = tk.Toplevel(fwin)
    win.geometry(f"300x300+{fwin.winfo_x()}+{fwin.winfo_y()}")
    win.wm_iconbitmap(ICO_PATH)
    win.title(HEAD+f"--tag group to {name}")

    cur = ex.conn.cursor()
    tag_data = cur.execute("SELECT TAG0IN, TAG0IF, TAG0GROUP0IN, TAG0GROUP0IF, IN0GROUP, NOTES, TYPE FROM TAG0GROUP WHERE NAME == ?;", (name, )).fetchall()[0]

    name_l = tk.Label(win, text=f"名称： {name}\t类型： {SQL.NAME_TYPE[tag_data[6]]}", style="Name.TLabel")
    note_l = tk.Label(win, text=tag_data[5], wraplength=win.winfo_width()-10, style="Notes.TLabel", anchor="nw")
    tag_in_f = tk.Frame(win, style="TagFrame.TFrame")
    tag_if_f = tk.Frame(win, style="TagFrame.TFrame")
    in_tag_f = tk.Frame(win, style="TagFrame.TFrame")

    name_l.grid(row=0, column=0, sticky="nsew")
    note_l.grid(row=1, column=0, sticky="nsew")
    tag_in_f.grid(row=2, column=0, sticky="nsew")
    tag_if_f.grid(row=3, column=0, sticky="nsew")
    in_tag_f.grid(row=4, column=0, sticky="nsew")
    win.columnconfigure(0, weight=1)
    win.rowconfigure(1, weight=1)
    win.rowconfigure(2, weight=4)
    win.rowconfigure(3, weight=4)
    win.rowconfigure(4, weight=2)

    tag0in_f = tk.Frame(tag_in_f, style="TagFrame.TFrame")
    tag0group0in_f = tk.Frame(tag_in_f, style="TagFrame.TFrame")
    tag0if_f = tk.Frame(tag_if_f, style="TagFrame.TFrame")
    tag0group0if_f = tk.Frame(tag_if_f, style="TagFrame.TFrame")

    tag0in_f.place(relx=0, rely=0, relwidth=1, relheight=0.5)
    tag0group0in_f.place(relx=0, rely=0.5, relwidth=1, relheight=0.5)
    tag0if_f.place(relx=0, rely=0, relwidth=1, relheight=0.5)
    tag0group0if_f.place(relx=0, rely=0.5, relwidth=1, relheight=0.5)

    def win_t(func: typing.Callable, n):
        def win__t():
            func(fwin, ex, n)
        return win__t

    tag_in = TagBox(win, tag0in_f, "包含tag：")
    for tag0 in SQL.to_r_tag(tag_data[0]):
        tag_in.add_tag(tag0, win_t(win_tag, tag0))
    tag_group_in = TagBox(win, tag0group0in_f, "包含tag group：")
    for tag1 in SQL.to_r_tag(tag_data[2]):
        tag_group_in.add_tag(tag1, win_t(win_tag0group, tag1))

    tag_if = TagBox(win, tag0if_f, "条件tag：")
    for tag3 in SQL.to_r_tag(tag_data[1]):
        tag_if.add_tag(tag3, win_t(win_tag, tag3))
    tag_group_if = TagBox(win, tag0group0if_f, "条件tag group：")
    for tag4 in SQL.to_r_tag(tag_data[3]):
        tag_group_if.add_tag(tag4, win_t(win_tag0group, tag4))

    in_tag = TagBox(win, in_tag_f, "位于以下tag group：")
    for tag5 in SQL.to_r_tag(tag_data[4]):
        in_tag.add_tag(tag5, win_t(win_tag0group, tag5))

    win.bind("<Enter>", lambda e: note_l.config(wraplength=win.winfo_width()-10))
    del tag_data
    cur.close()
    win.mainloop()
    return win
def win_file(fwin: tk.Tk | tk.Toplevel, ex: SQL.Explorer, uid: int, base_url: str) -> tk.Toplevel:
    """file的细节描述界面"""
    cur = ex.conn.cursor()
    file_data = cur.execute("SELECT NAME, TYPE, SOURCE, TAG, TAG0GROUP, NOTES FROM FILE WHERE UID == ?;", (uid, )).fetchall()[0]
    image = get_file_cover(os.path.join(base_url, str(uid)), file_data[1], (140, 200))

    win = tk.Toplevel(fwin)
    win.geometry(f"600x300+{fwin.winfo_x()}+{fwin.winfo_y()}")
    win.wm_iconbitmap(ICO_PATH)
    win.title(HEAD+f"--file to "+"%05d"%uid)

    base_f = tk.Frame(win, style="TagFrame.TFrame")
    data_f = tk.Frame(win, style="TagFrame.TFrame")
    base_f.grid(row=0, column=0, sticky="nsew")
    data_f.grid(row=0, column=1, sticky="nsew")
    win.rowconfigure(0, weight=1)
    win.columnconfigure(1, weight=1)

    image_l = tk.Label(base_f, image=image, width=140)

    message_f = tk.Frame(base_f, style="TagMessageFrame.TFrame")
    uid_l = tk.Label(message_f, text=f"uid： {"%05d"%uid}", style="Name.TLabel", anchor="nw")
    name_l = tk.Label(message_f, text=f"名称： {file_data[0]}", style="Name.TLabel")
    type_l = tk.Label(message_f, text=f"类型： {SQL.NAME_FILE_TYPE[file_data[1]]}", style="Name.TLabel")

    image_l.grid(row=0, column=0, sticky="nsew")
    message_f.grid(row=1, column=0, sticky="nsew")
    base_f.rowconfigure(1, weight=1)
    uid_l.grid(row=1, column=0, sticky="nsew")
    name_l.grid(row=2, column=0, sticky="nsew")
    type_l.grid(row=3, column=0, sticky="nsew")

    note_l = tk.Label(data_f, text=f"{file_data[2]}\n"
                                   f"{file_data[5]}", style="Notes.TLabel", anchor="nw")
    # 因为不考虑新增Tag类型，这一段是写死的
    tag_writer_f = tk.Frame(data_f, style="TagFrame.TFrame")
    tag_actor_f = tk.Frame(data_f, style="TagFrame.TFrame")
    tag_works_f = tk.Frame(data_f, style="TagFrame.TFrame")
    tag_tags_f = tk.Frame(data_f, style="TagFrame.TFrame")

    note_l.place(relx=0, rely=0, relwidth=1, relheight=0.3)
    tag_works_f.place(relx=0, rely=0.3, relwidth=1, relheight=0.1)
    tag_actor_f.place(relx=0, rely=0.4, relwidth=1, relheight=0.2)
    tag_writer_f.place(relx=0, rely=0.6, relwidth=1, relheight=0.1)
    tag_tags_f.place(relx=0, rely=0.7, relwidth=1, relheight=0.3)

    tag_d = cur.execute(f"SELECT NAME, TYPE FROM TAG WHERE NAME IN {SQL.SQL.to_tuple(SQL.to_r_tag(file_data[3]))};").fetchall()
    tag0group_d = cur.execute(f"SELECT NAME, TYPE FROM TAG0GROUP WHERE NAME IN {SQL.SQL.to_tuple(SQL.to_r_tag(file_data[4]))};").fetchall()

    def win_t(func: typing.Callable, n):
        def win__t():
            func(fwin, ex, n)
        return win__t
    tag_writer_in = TagBox(win, tag_writer_f, "艺术家：")
    tag_actor_in = TagBox(win, tag_actor_f, "角色：")
    tag_works_in = TagBox(win, tag_works_f, "作品：")
    tag_tags_in = TagBox(win, tag_tags_f, "标签：")
    for _n, _t in tag_d:
        if _t == SQL.TYPE_WRITER:
            tag_writer_in.add_tag(_n, win_t(win_tag, _n))
        elif _t == SQL.TYPE_ACTOR:
            tag_actor_in.add_tag(_n, win_t(win_tag, _n))
        elif _t == SQL.TYPE_WORKS:
            tag_works_in.add_tag(_n, win_t(win_tag, _n))
        else:
            tag_tags_in.add_tag(_n, win_t(win_tag, _n))
    for _n, _t in tag0group_d:
        if _t == SQL.TYPE_WRITER:
            tag_writer_in.add_tag(_n, win_t(win_tag0group, _n))
        elif _t == SQL.TYPE_ACTOR:
            tag_actor_in.add_tag(_n, win_t(win_tag0group, _n))
        elif _t == SQL.TYPE_WORKS:
            tag_works_in.add_tag(_n, win_t(win_tag0group, _n))
        else:
            tag_tags_in.add_tag(_n, win_t(win_tag0group, _n))

    win.bind("<Enter>", lambda e: note_l.config(wraplength=win.winfo_width()-10))
    cur.close()
    win.mainloop()
    return win

class TagBox:
    """
    塞入多个可点击自适应排序Tag的frame
    """
    def __init__(self, win: tk.Toplevel | tk.Tk, frame: tk.Frame, head_text: str, is_head: bool=False, is_id: bool=False):
        """
        is_head 询问head是否单独成行\n
        is_id 打开id管理器，运行通过赋予id进行删除等高级操作，在添加时需加入唯一性id
        """
        self.win = win
        self.main_f = frame
        self.is_head = is_head
        self.font = tk.font.Font(font="TkDefaultFont")
        self.is_id = is_id
        self.is_w = True
        if self.is_id:
            self.tag_d = {}  # type: dict[typing.Any :tuple[tk.Button, int]]
        else:
            self.tag_l = []  # type: list[tuple[tk.Button, int]]

        self.head = tk.Label(self.main_f, text=head_text, style="TagBoxHead.TLabel", font=self.font)
        self.head.place(x=0, y=0, width=self.font.measure(head_text))
        self.main_f.bind("<Configure>", lambda e: self.fresh())

    def add_tag(self, name: str, command: typing.Callable, right_command: typing.Callable|None=None, uid=None):
        if not self.is_w:
            return
        b = tk.Button(self.main_f, text=name, style="TagBox.TButton", command=command)
        if self.is_id:
            if uid in self.tag_d.keys():
                self.tag_d[uid][0].destroy()
                del self.tag_d[uid]
            self.tag_d[uid] = (b, self.font.measure(name))
        else:
            self.tag_l.append((b, self.font.measure(name)))
        if right_command:
            b.bind("<Button-3>", right_command)
        self.fresh()

    def del_tag(self, uid: typing.Any):
        """删除指定id的tag，仅在is_id为True时有效"""
        if not self.is_w:
            return
        if self.is_id:
            self.tag_d[uid][0].destroy()
            del self.tag_d[uid]
            self.fresh()
    def get_tag(self):
        """获取所有tag"""
        if self.is_id:
            return [z[0].cget("text") for z in self.tag_d.values()]
        else:
            return [z[0].cget("text") for z in self.tag_l]
    def fresh(self):
        """重新为tag排序"""
        self.win.update()
        _padx = 2  # 间隔长
        h, this_y = 30, 0
        all_w, this_w = self.main_f.winfo_width(), self.head.winfo_width()
        if self.is_head:
            this_y += h
            this_w = 0
        if self.is_id:
            tag = self.tag_d.values()
        else:
            tag = self.tag_l
        for _b, _len in tag:
            new_w = this_w + _padx + _len + 15
            if new_w >= all_w:
                this_w = 0
                this_y += h
                new_w = _padx + _len + 15
            _b.place(x=this_w + _padx, y=this_y, width=_len + 15)
            this_w = new_w

    def write_yes(self, is_w: bool=True):
        """设置是否可写"""
        self.is_w = is_w
    def clear(self):
        """清空所有tag"""
        if self.is_id:
            for z in self.tag_d.values():
                z[0].destroy()
            self.tag_d.clear()
        else:
            for z in self.tag_l:
                z[0].destroy()
            self.tag_l.clear()
        self.fresh()
class SearchTagBox:
    """
    通用的检索窗口\n
    左键事件：打开详情窗口\n
    检索项右键事件：添加至目标表\n
    递交右键事件：删除tag
    """
    def __init__(self, win: tk.Toplevel | tk.Tk, frame: tk.Frame, ex: SQL.Explorer,
                 tag_list_in: TagBox, tag0group_list_in: TagBox,
                 input_text: str="追加tag：",
                 set_message: typing.Callable[[str, str], None]=lambda x, y: None):
        """
        :param win: frame的父窗口
        :param frame: 一个空frame，显示该类内容
        :param ex: 文件库指针
        :param tag_list_in: tag检索选中结果将提交至此
        :param tag0group_list_in: tag0group检索选中结果将提交至此
        :param input_text: 输入框文本
        :param set_message: 可能的消息显示函数
        """
        self.win = win
        self.main_f = frame
        self.ex = ex

        self.tag_list_in = tag_list_in
        self.tag0group_list_in = tag0group_list_in

        self.cur = self.ex.conn.cursor()
        self.tag_s = tk.StringVar()  # 查找tag的临时输入
        self.set_message = set_message

        tk.Label(self.main_f, text=input_text, style="MainBase.TLabel").grid(row=0, column=0, padx=2, pady=2)
        tk.Entry(self.main_f, textvariable=self.tag_s, width=20).grid(row=0, column=1, padx=2, pady=2, sticky="nsew")
        self.s_tag_f = tk.Frame(self.main_f, style="TagFrame.TFrame")
        self.s_tag_f.grid(row=2, column=0, columnspan=2, padx=2, pady=2, sticky="nsew")
        self.s_tag0group_f = tk.Frame(self.main_f, style="TagFrame.TFrame")
        self.s_tag0group_f.grid(row=3, column=0, columnspan=2, padx=2, pady=2, sticky="nsew")
        self.main_f.rowconfigure(2, weight=1)
        self.main_f.rowconfigure(3, weight=1)
        self.main_f.columnconfigure(1, weight=1)

        self.s_tag_in = TagBox(self.win, self.s_tag_f, "tag: ", is_id=True)
        self.s_tag0group_in = TagBox(self.win, self.s_tag0group_f, "tag0group: ", is_id=True)

        self.tag_s.trace_add("write", self.search_tags)

    def tags_command(self, func: typing.Callable, n: str):
        def left():
            self.set_message(f"左键点击打开详情，右键点击将此项添加至检索表/删除tag", "gray")
            func(self.win, self.ex, name=n)
        return left

    def tags_right_command(self, _in: TagBox, uid):
        def right(e):
            self.set_message(f"左键点击打开详情，右键点击将此项添加至检索表/删除tag", "gray")
            _in.del_tag(uid=uid)
            _in.fresh()

        return right
    def list_tags(self, n: str, _type: typing.Literal["tag", "tag0group"]):
        """
        为list_in添加tag
        同时，tag名与id相同以清空重复项
        """
        if _type == "tag":
            if n in self.tag_list_in.tag_d:
                return
            self.tag_list_in.add_tag(n, uid=n,
                                command=self.tags_command(win_tag, n),
                                right_command=self.tags_right_command(self.tag_list_in, n))
            self.tag_list_in.fresh()
        else:
            if n in self.tag0group_list_in.tag_d:
                return
            self.tag0group_list_in.add_tag(n, uid=n,
                                      command=self.tags_command(win_tag0group, n),
                                      right_command=self.tags_right_command(self.tag0group_list_in, n))
            self.tag0group_list_in.fresh()

    def search_tags_right_command(self, n: str, _type: typing.Literal["tag", "tag0group"]):
        def right(e):
            self.set_message(f"左键点击打开详情，右键点击将此项添加至检索表/删除tag", "gray")
            self.list_tags(n, _type)

        return right

    def search_tags(self, *args):
        """更新tag检索"""
        tag_name = HanziConv.toSimplified(self.tag_s.get())
        if not tag_name:
            self.s_tag_in.clear()
            self.s_tag0group_in.clear()
            return
        self.tag_s.set(tag_name)
        tag_l = self.cur.execute(f"SELECT NAME FROM TAG WHERE NAME GLOB(\"*{tag_name}*\")").fetchall()
        tag0group_l = self.cur.execute(f"SELECT NAME FROM TAG0GROUP WHERE NAME GLOB(\"*{tag_name}*\")").fetchall()
        self.s_tag_in.clear()
        self.s_tag0group_in.clear()
        for i_tag in range(len(tag_l)):
            self.s_tag_in.add_tag(tag_l[i_tag][0], uid=i_tag,
                             command=self.tags_command(win_tag, tag_l[i_tag][0]),
                             right_command=self.search_tags_right_command(tag_l[i_tag][0], "tag"))
        for i_tag in range(len(tag0group_l)):
            self.s_tag0group_in.add_tag(tag0group_l[i_tag][0], uid=i_tag,
                                   command=self.tags_command(win_tag0group, tag0group_l[i_tag][0]),
                                   right_command=self.search_tags_right_command(tag0group_l[i_tag][0], "tag0group"))
        self.s_tag_in.fresh()
        self.s_tag0group_in.fresh()
    def __del__(self):
        self.cur.close()
class SearchBoxToTkListbox:
    """
    检索窗口，供tk.Listbox使用
    """

    def __init__(self, win: tk.Toplevel | tk.Tk, frame: tk.Frame, ex: SQL.Explorer,
                 _type: typing.Literal["tag", "file"], lb: list[tk.Listbox],
                 input_text: str = "追加tag：",
                 set_message: typing.Callable[[str, str], None] = lambda x, y: None):
        """
        :param win: frame的父窗口
        :param frame: 一个空frame，显示该类内容
        :param ex: 文件库指针
        :param _type: 检索类型，tag或file
        :param lb: 目标列表框
        :param input_text: 输入框文本
        :param set_message: 可能的消息显示函数
        """
        self.win = win
        self.main_f = frame
        self.ex = ex
        self.cur = self.ex.conn.cursor()
        self.message = set_message
        self.lb = lb

        self.is_input = True  # 是否注入
        self._type = _type

        self.tag_s = tk.StringVar()  # 查找tag的临时输入
        tk.Label(self.main_f, text=input_text, style="MainBase.TLabel").grid(row=0, column=0, padx=2, pady=2)
        tk.Entry(self.main_f, textvariable=self.tag_s, width=20).grid(row=0, column=1, padx=2, pady=2, sticky="nsew")
        self.boxes = []
        if _type == "tag":
            s_tag_f = tk.Frame(self.main_f, style="TagFrame.TFrame")
            s_tag_f.grid(row=2, column=0, columnspan=2, padx=2, pady=2, sticky="nsew")
            s_tag0group_f = tk.Frame(self.main_f, style="TagFrame.TFrame")
            s_tag0group_f.grid(row=3, column=0, columnspan=2, padx=2, pady=2, sticky="nsew")
            self.main_f.rowconfigure(2, weight=1)
            self.main_f.rowconfigure(3, weight=1)
            self.main_f.columnconfigure(1, weight=1)

            self.boxes.append(TagBox(self.win, s_tag_f, "tag: ", is_id=True))
            self.boxes.append(TagBox(self.win, s_tag0group_f, "tag0group: ", is_id=True))
        elif _type == "file":
            s_file_f = tk.Frame(self.main_f, style="TagFrame.TFrame")
            s_file_f.grid(row=2, column=0, columnspan=2, padx=2, pady=2, sticky="nsew")
            self.main_f.rowconfigure(2, weight=1)
            self.main_f.columnconfigure(1, weight=1)

            self.boxes.append(TagBox(self.win, s_file_f, "file: ", is_id=True))
        self.tag_s.trace_add("write", self.search)
    def search(self, *args):
        key = HanziConv.toSimplified(self.tag_s.get())
        for i in self.boxes:
            i.clear()
        if not key:
            return
        self.tag_s.set(key)
        if self._type == "tag":
            tag_l = self.cur.execute(f"SELECT NAME FROM TAG WHERE NAME GLOB(\"*{key}*\")").fetchall()
            tag0group_l = self.cur.execute(f"SELECT NAME FROM TAG0GROUP WHERE NAME GLOB(\"*{key}*\")").fetchall()
            for i_tag in range(len(tag_l)):
                self.boxes[0].add_tag(tag_l[i_tag][0], uid=i_tag,
                                      command=self.command(win_tag, self.win, self.ex, tag_l[i_tag][0]),
                                      right_command=self.right_command(tag_l[i_tag][0], "tag"))
            for i_tag in range(len(tag0group_l)):
                self.boxes[1].add_tag(tag0group_l[i_tag][0], uid=i_tag,
                                      command=self.command(win_tag0group, self.win, self.ex, tag0group_l[i_tag][0]),
                                      right_command=self.right_command(tag0group_l[i_tag][0], "tag0group"))
        elif self._type == "file":
            file_l = self.cur.execute(f"SELECT NAME, UID FROM FILE WHERE NAME GLOB(\"*{key}*\")").fetchall()
            for i_file in range(len(file_l)):
                self.boxes[0].add_tag(f"{file_l[i_file][1]}: {file_l[i_file][0]}", uid=i_file,
                                      command=self.command(win_file, self.win, self.ex, file_l[i_file][1], self.ex.url_file),
                                      right_command=self.right_command(f"{file_l[i_file][1]}: {file_l[i_file][0]}", "file"))

    def command(self, win, *n) -> typing.Callable:
        def left():
            self.message(f"左键点击打开详情，右键点击将此项添加至检索表", "gray")
            win(*n)
        return left
    def right_command(self, param, _type: typing.Literal["tag", "tag0group", "file"]):
        if _type == "tag":
            def right(e):
                if self.is_input:
                    l = self.lb[0].get(0, tk.END)
                    if param not in l:
                        self.lb[0].insert(tk.END, param)
        elif _type == "tag0group":
            def right(e):
                if self.is_input:
                    l = self.lb[1].get(0, tk.END)
                    if param not in l:
                        self.lb[1].insert(tk.END, param)
        else:
            def right(e):
                if self.is_input:
                    l = self.lb[0].get(0, tk.END)
                    if param not in l:
                        self.lb[0].insert(tk.END, param)
        return right
    def set_write(self, is_input: bool):
        self.is_input = is_input

class ListBox:
    """
    一个带滚动条的特殊列表
    """
    def __init__(self, win: tk.Toplevel | tk.Tk, frame: tk.Frame):
        self.win = win
        self.main_f = frame
        self.f00_height = 0  # 初始元素的高
        self.f00_opposite_y = 0  # y轴起点, 为方便计算为其反值
        self.len = 0  # row数
        self.is_f_fresh = False  # 是否存在fresh Frame

        self.image = []  # 可能的图像引用

        self.var_fresh = {
            "tag_notes": []
        }

        self.scrollbar = tk.Frame(self.main_f)
        self.show = tk.Frame(self.main_f)

        self.scrollbar.pack(side="right", fill="y")
        self.show.pack(side="left", expand=True, fill="both")

        self.scrollbar_true = tk.Scrollbar(self.scrollbar, command=self.__scrollbar_command)
        self.f00 = tk.Frame(self.show)
        self.win_old_w = self.f00.winfo_width()  # 旧win长
        self.scrollbar_true.pack(expand=True, fill="both")
        self.f00.place(x=0, y=-self.f00_opposite_y, relwidth=1, height=self.f00_height)
        self.f00.columnconfigure(index=0, weight=1)
        # 事件表
        self.scrollbar_true.bind("<Button-1>", self.__scrollbar_click)
        self.scrollbar_true.bind("<B1-Motion>", self.__scrollbar_click)
        self.win.bind("<MouseWheel>", self.__scrollbar_slip)
        self.win.bind("<<fresh>>", lambda e: self.fresh())
        self.win.bind("<Enter>", lambda e: self.fresh())

        self.win.update()
        self.fresh()

    def __apply_frame(self, h: int) -> tuple[tk.Frame, tk.Separator]:
        self.f00_height += h + 2
        self.f00.place(height=self.f00_height, y=-self.f00_opposite_y)

        f = tk.Frame(self.f00, height=h, style="ListBox.TFrame")
        f.grid(column=0, row=self.len, sticky='ew')
        f.grid_propagate(False)
        self.len += 1

        s = tk.Separator(self.f00, style="ListBoxF.TSeparator")
        s.grid(column=0, row=self.len, sticky='ew')
        s.grid_propagate(False)
        self.len += 1

        return f, s
    def __del_frame_height(self, h: int):
        """删去指定高frame对总高的影响"""
        self.f00_height -= h + 2

    def add_fresh(self, text: str="刷新更多", fresh_event=None):
        null, s = self.__apply_frame(25)
        s.grid_forget()
        self.len -= 2
        text = tk.Label(null, text=text, anchor="n")
        text["foreground"] = "orange"
        text.place(relx=0, rely=0, relwidth=1, relheight=1)

        def enter(e): text["foreground"] = "blue"
        def leave(e): text["foreground"] = "orange"
        text.bind("<Enter>", enter)
        text.bind("<Leave>", leave)
        if fresh_event:
            text.bind("<Button-1>", fresh_event)
        if self.is_f_fresh:
            self.__del_frame_height(25)
        else:
            self.is_f_fresh = True

    def add_tag(self, name: str, notes: str, ex: SQL.Explorer):
        f = self.__apply_frame(55)[0]
        name = tk.StringVar(value=name)
        name_l = tk.Entry(f, textvariable=name, style="ListBoxName.TEntry",
                          state="readonly", justify="center")
        notes_e = tk.Label(f, text=notes, style="ListBoxNotes.TLabel")
        but = tk.Button(f, text="详情", command=lambda : win_tag(self.win, ex, name.get()), style="ListBoxXQ.TButton")

        name_l.place(relx=0, rely=0, relwidth=0.2, relheight=1)
        notes_e.place(relx=0.2, rely=0, relwidth=0.6, relheight=1)
        but.place(relx=0.8, rely=0.2, relwidth=0.2)

        self.var_fresh["tag_notes"].append(notes_e)
    def add_tag0group(self, name: str, tag0in: str, tag0if: str, tag0group0in: str, tag0group0if: str, notes: str, ex: SQL.Explorer):
        tag0in = SQL.to_r_tag(tag0in)
        tag0if = SQL.to_r_tag(tag0if)
        tag0group0in = SQL.to_r_tag(tag0group0in)
        tag0group0if = SQL.to_r_tag(tag0group0if)

        f = self.__apply_frame(120)[0]
        right_f = tk.Frame(f, style="ListBox.TFrame")
        left_f = tk.Frame(f, style="ListBox.TFrame")
        right_f.place(relx=0.7, rely=0, relwidth=0.3, relheight=1)
        left_f.place(relx=0, rely=0, relwidth=0.7, relheight=1)

        notes_l = tk.Label(right_f, text=notes, style="ListBoxNotes.TLabel", anchor="nw")
        but = tk.Button(right_f, text="详情", command=lambda : win_tag0group(self.win, ex, name.get()), style="ListBoxXQ.TButton")
        but.pack(side="bottom", fill="x")
        notes_l.pack(side="top", fill="both", expand=True)

        name = tk.StringVar(value=name)
        name_e = tk.Entry(left_f, textvariable=name, style="ListBoxName.TEntry",
                          state="readonly", justify="center")
        name_e.pack(side="top", fill="x")

        tag_f = tk.Frame(left_f, style="ListBox.TFrame")
        tag_f.pack(side="top", fill="both", expand=True)
        tag_in_f = tk.Frame(tag_f, style="ListBox.TFrame")
        tag_if_f = tk.Frame(tag_f, style="ListBox.TFrame")
        tag_in_f.place(relx=0, rely=0, relwidth=1, relheight=0.5)
        tag_if_f.place(relx=0, rely=0.5, relwidth=1, relheight=1)
        tag_in = TagBox(self.win, tag_in_f, "包含子项：")
        tag_if = TagBox(self.win, tag_if_f, "条件：")
        def win_t(func: typing.Callable, n):
            def win__t():
                func(self.win, ex, n)
            return win__t
        for _tag0in in tag0in:
            tag_in.add_tag(_tag0in, win_t(win_tag, _tag0in))
        for _tag0group0in in tag0group0in:
            tag_in.add_tag(_tag0group0in, win_t(win_tag0group, _tag0group0in))
        for _tag0if in tag0if:
            tag_if.add_tag(_tag0if, win_t(win_tag, _tag0if))
        for _tag0group0if in tag0group0if:
            tag_if.add_tag(_tag0group0if, win_t(win_tag0group, _tag0group0if))
    def add_file(self, uid: int, name: str, _type: int, source: str, tag: str, tag0group: str, notes: str, ex: SQL.Explorer):
        url_dir = str(os.path.join(ex.url_file, str(uid)))
        image = get_file_cover(url_dir, _type, (120, 150))
        self.image.append(image)
        f = self.__apply_frame(150)[0]
        image_l = tk.Label(f, image=image)
        data_f = tk.Frame(f, style="ListBox.TFrame")
        name_l = tk.Label(data_f, text="名称："+name, style="ListBoxName.TLabel", anchor="w")
        type_l = tk.Label(data_f, text="类型："+SQL.NAME_FILE_TYPE[_type], style="ListBoxType.TLabel", anchor="w")
        notes_l = tk.Label(data_f, text=f"{source}\n{notes}", style="ListBoxNotes.TLabel", anchor="nw")
        self.var_fresh["tag_notes"].append(notes_l)
        tag_in_f = tk.Frame(data_f, style="ListBoxFileTag.TFrame")
        tag_in = TagBox(self.win, tag_in_f, "")
        def win_t(func: typing.Callable, n):
            def win__t():
                func(self.win, ex, n)
            return win__t
        for _tag in SQL.to_r_tag(tag):
            tag_in.add_tag(_tag, win_t(win_tag, _tag))
        for _tag0group in SQL.to_r_tag(tag0group):
            tag_in.add_tag(_tag0group, win_t(win_tag0group, _tag0group))
        data_file_f = tk.Frame(data_f, style="ListBox.TFrame")
        def open_dir(): os.startfile(url_dir)
        uid_l = tk.Label(data_file_f, text=f"ID：{uid}", style="ListBoxName.TLabel", anchor="w")
        but1 = tk.Button(data_file_f, text="打开目录", command=open_dir, style="ListBoxXQ.TButton")
        but2 = tk.Button(data_file_f, text="详情", command=lambda : win_file(self.win, ex, uid, ex.url_file), style="ListBoxXQ.TButton")
        uid_l.place(relx=0, rely=0, relwidth=1, relheight=0.2)
        but2.pack(side="bottom", fill="x")
        but1.pack(side="bottom", fill="x")

        image_l.pack(side="left", fill="y")
        data_f.pack(side="left", fill="both", expand=True)
        name_l.place(relx=0, rely=0, relwidth=0.4, relheight=0.2)
        type_l.place(relx=0.4, rely=0, relwidth=0.4, relheight=0.2)
        notes_l.place(relx=0, rely=0.2, relwidth=0.8, relheight=0.4)
        tag_in_f.place(relx=0, rely=0.6, relwidth=0.8, relheight=0.4)
        data_file_f.place(relx=0.8, rely=0, relwidth=0.2, relheight=1)

    def add_tags_and_fresh(self, _data: list[tuple[str, str]], ex: SQL.Explorer, text: str="刷新更多", fresh_event=None):
        for n, nt in _data:
            self.add_tag(n, nt, ex)
        self.add_fresh(text, fresh_event)
        self.win.after(100, self.fresh)
    def add_tag0groups_and_fresh(self, _data: list[tuple], ex: SQL.Explorer, text: str="刷新更多", fresh_event=None):
        for _d in _data:
            self.add_tag0group(*_d, ex=ex)
        self.add_fresh(text, fresh_event)
        self.win.after(100, self.fresh)
    def add_files_and_fresh(self, _data: list[tuple], ex: SQL.Explorer, text: str="刷新更多", fresh_event=None):
        for _d in _data:
            self.add_file(*_d, ex=ex)
        self.add_fresh(text, fresh_event)
        self.win.after(100, self.fresh)

    def clear(self):
        for t in self.f00.winfo_children():
            t.destroy()
        self.f00_height = 0
        self.f00_opposite_y = 0
        self.len = 0
        self.is_f_fresh = False
        self.var_fresh = {
            "tag_notes": []
        }
        self.image.clear()

    def __get_scrollbar_pos(self) -> tuple[float, float]:
        """获取逻辑scrollbar滑块的位置"""
        all_h = self.show.winfo_height()
        top = self.f00_opposite_y / self.f00_height
        length = all_h / self.f00_height
        return top, top + length

    def fresh(self):
        """更新一次组件状态"""
        self.f00.place(height=self.f00_height, y=-self.f00_opposite_y)

        all_h = self.show.winfo_height()
        if all_h >= self.f00_height:
            self.scrollbar_true.set(1e-4, 1)  # 0-1存在显示bug，改用一个极小值
        else:
            self.scrollbar_true.set(*self.__get_scrollbar_pos())
        self.__check_wraplength()

    def __scrollbar_click(self, event):
        """左键点击(放下)或长按拖动"""
        all_h = self.show.winfo_height()
        if all_h >= self.f00_height:
            self.fresh()
        else:
            s_h = self.scrollbar_true.winfo_height()
            this = event.y / s_h
            self.f00_opposite_y = self.__check_y(self.f00_height * this, all_h)
            self.fresh()

    def __scrollbar_slip(self, event):
        """滚动"""
        all_h = self.show.winfo_height()
        if all_h >= self.f00_height:
            self.fresh()
        else:
            y = self.f00_opposite_y
            if event.delta < 0:
                y += 20
            else:
                y -= 20
            self.f00_opposite_y = self.__check_y(y, all_h)
            self.fresh()

    def __scrollbar_command(self, *args):
        flag = -1 if args[1][0] == "-" else 1
        self.__scrollbar_slip(SimpleNamespace(delta=flag * -120))

    def __check_y(self, y: int | float, all_h: int) -> int:
        """为y位置做校验"""
        y = int(y)
        if y < 0:
            y = 0
        elif y + all_h > self.f00_height:
            y = self.f00_height - all_h
        return y

    def __check_wraplength(self):
        """更新子项中wraplength的数值"""
        _vars = self.var_fresh["tag_notes"]
        if abs(self.f00.winfo_width()-self.win_old_w) < 2 or not _vars:
            return
        else:
            self.win_old_w = self.f00.winfo_width()

        for _var in _vars:
            _length = _var.winfo_width()
            _var["wraplength"] = _length
    def fresh_wraplength(self):
        _vars = self.var_fresh["tag_notes"]
        for _var in _vars:
            _length = _var.winfo_width()
            _var["wraplength"] = _length
        self.win.update()

class GUI:
    def __init__(self, size: tuple[int, int]):
        try:
            with open(os.path.join(THIS_PATH, "save.json"), "r", encoding="utf-8") as f:
                self.json = json.loads(f.read())
        except OSError:
            with open(os.path.join(THIS_PATH, "save.json"), "w", encoding="utf-8") as f:
                f.write(json.dumps(DEFAULT_SAVE_JSON, ensure_ascii = False, indent = 4))
                self.json = DEFAULT_SAVE_JSON

        self.main_ex = self.win_get_folder()
        self.win_size = size

        self.BaseCrawlerRule = CrawlerAPI.CrawlerRule()
        self.BaseCrawlerRule.update_replaceRule("[BaseUrl]", os.path.join(THIS_PATH, "crawler"))
        self.BaseCrawlerRule.update_replaceRule("[DataUrl]", self.main_ex.url_scratch)
        self.crawlers = CrawlerAPI.read_file_crawler(os.path.join(THIS_PATH, "save.json"), self.BaseCrawlerRule)
        # 主要模块
        self.root = tk.Tk()
        self.root.geometry(self.get_center(*self.win_size))
        self.root.title(HEAD)
        self.root["background"] = "#F8F8FF"
        self.root.wm_iconbitmap(ICO_PATH)
        self.root.minsize(400, 300)
        self.root.option_add('*tearOff', False)

        self.img = []
        # 字体与样式
        self.font = dict()
        self.font["message"] = tk.font.Font(family="楷体", size=10)
        self.font["search"] = tk.font.Font(family="TkDefaultFont", size=10)
        self.font["name"] = tk.font.Font(family="宋体", size=20)
        self.font["describe"] = tk.font.Font(family="宋体", size=12)
        self.style = init_style()
        # Menu
        self.root_menu = tk.Menu(self.root)
        menu_info = tk.Menu(self.root_menu)
        self.root["menu"] = self.root_menu

        self.root_menu.add_command(label="Tag表", command=self.win_tag)
        self.root_menu.add_command(label="Tag管理", command=self.win_set_tag)
        self.is_win_set_tag = False  # 查看set_tag窗口是否打开，SQL不允许异步
        self.root_menu.add_command(label="|", state="disabled")
        self.root_menu.add_command(label="下载", command=self.win_crawler)
        self.root_menu.add_command(label="|", state="disabled")
        self.root_menu.add_command(label="库合并", command=self.win_merge)
        self.root_menu.add_command(label="|", state="disabled")
        self.root_menu.add_cascade(menu=menu_info, label="帮助")
        menu_info.add_command(label="关于项目", command=lambda :webbrowser.open(r"https://github.com/Be-omitted/StrangeExplorer"))
        # 界面分割
        self.root_message = tk.Label(self.root, text="...", background="#DCDCDC", font=self.font["message"], foreground="gray")
        self.root_main_notebook = tk.Notebook(self.root, style="Main.TNotebook")

        self.root_main_notebook.pack(side="top", fill="both", expand=True)
        self.root_message.pack(side="bottom", fill="x")

        self.root_main_homepage = self.set_main_notebook("主页")
        self.root_main_save = self.set_main_notebook("库存")
        self.root_main_download_manage = self.set_main_notebook("管理")
        self.root_main_output = self.set_main_notebook("副本")

        self.__main_homepage()
        self.__main_save()
        self.__main_download_manage()
        self.__main_output()

        self.set_message("初次使用请查询相关网页的帮助信息")

    def set_main_notebook(self, text: str) -> tk.Frame:
        f = tk.Frame(self.root)
        self.root_main_notebook.add(f, text=text)
        return f
    def set_message(self, text: str, color: str="gray"):
        """更改message文本"""
        self.root_message["text"] = text
        self.root_message["foreground"] = color

    def win_get_folder(self) -> SQL.Explorer:
        """唤起一个文件库选择窗口，并返回对应的Explorer对象"""
        win = tk.Tk()
        win.wm_iconbitmap(ICO_PATH)
        win.geometry(self.get_center(350, 150))
        win.wm_title(HEAD + "--选择主文件库")
        folder = tk.StringVar()
        folder.set(self.json["history_path"] if "history_path" in self.json else "")
        tips = tk.StringVar()
        tips.set("如无文件库，请选择一个空文件夹用以存放")
        _ex = []

        def verify(_is: bool, ex: list):
            if os.path.isdir(folder.get()):
                if _is:
                    if SQL.is_explorer(folder.get()):
                        tips.set("这已经是一个文件库了")
                    else:
                        ex.append(SQL.Explorer(folder.get(), True))
                        win.quit()
                else:
                    if SQL.is_explorer(folder.get()):
                        ex.append(SQL.Explorer(folder.get(), False))
                        win.quit()
                    else:
                        tips.set("此目录不是合法的文件库，请选择新建文件库")
            else:
                tips.set("请输入合法且存在的目录地址")

        fa1 = tk.Frame(win)
        fa2 = tk.Frame(win)
        fa3 = tk.Frame(win)
        fa1.grid(row=0, column=0), fa2.grid(row=1, column=0), fa3.grid(row=2, column=0)
        win.columnconfigure(0, weight=1)

        tk.Label(fa1, text="选择文件库").grid(row=1, column=0)
        main_entry = tk.Entry(fa1, textvariable=folder)
        main_entry.grid(row=1, column=1, padx=5, pady=5)
        main_entry.focus()

        tk.Button(fa1, text='打开目录', command=lambda: folder.set(tk.askdirectory())).grid(row=1, column=2)
        fa1.columnconfigure(1, weight=1)
        tk.Button(fa2, text="以此文件夹进入", width=30, command=lambda: verify(False, _ex)).grid(row=0)
        tk.Button(fa2, text="在此文件夹创建新文件库并进入", width=30, command=lambda: verify(True, _ex)).grid(row=1)
        tk.Button(fa2, text="退出", width=30, command=sys.exit).grid(row=2)

        tk.Label(fa3, textvariable=tips, foreground="gray").grid(row=0)

        win.mainloop(0)
        self.json["history_path"] = folder.get()
        with open(os.path.join(THIS_PATH, "save.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(self.json))

        win.destroy()
        del win
        del folder
        return _ex.pop(0)
    def win_tag(self):
        """返回一个tag表的子窗口"""
        cur = self.main_ex.conn.cursor()

        win = tk.Toplevel(self.root)
        win.geometry(self.get_center(400, 600))
        win.title(HEAD + "--Tag表")
        win["background"] = "#F8F8FF"
        win.wm_iconbitmap(ICO_PATH)

        is_tag = tk.BooleanVar()
        num = tk.IntVar()
        search = tk.StringVar()
        scope = tk.StringVar()
        is_tag.set(True)
        num.set(0)
        search.set("")
        scope.set("名称")

        win_f1 = tk.Frame(win)
        win_f2 = tk.Frame(win, style="tagf00.TFrame")
        win_f1.pack(side="top", fill="x")
        tk.Separator(win, orient=tk.HORIZONTAL).pack(fill="x", pady=3)
        win_f2.pack(side="top", expand=True, fill="both")
        # 搜索栏
        space_ = tk.Combobox(win_f1, textvariable=scope, width=5, font=self.font["search"],
                             values=("名称", "描述", "全部"))
        tk.Entry(win_f1, textvariable=search, font=self.font["search"]).grid(column=5, row=0, sticky="wnes", padx=2)
        but_search = tk.Button(win_f1, text="搜索", command=None)  # 此处command在后文被替换
        but_search.grid(column=10, row=0, sticky="ns")

        win_f1.columnconfigure(5, weight=1)
        win_f1.rowconfigure(0, weight=1)
        space_.grid(column=0, row=0, sticky="ns")
        space_.state(["readonly"])
        # 显示区
        _main = ListBox(win, win_f2)

        # 钩子
        def add_tag_50():
            _start = num.get()
            _key = scope.get()
            if _key == "名称":
                z = HanziConv.toSimplified(search.get())
                search.set(z)
                values = cur.execute(f"SELECT NAME, NOTES FROM TAG WHERE NAME GLOB(\"*{search.get()}*\") LIMIT {_start+50};").fetchall()
            elif _key == "描述":
                values = cur.execute(f"SELECT NAME, NOTES FROM TAG WHERE NOTES GLOB(\"*{search.get()}*\") LIMIT {_start+50};").fetchall()
            else:
                values = cur.execute(f"SELECT NAME, NOTES FROM TAG WHERE NOTES GLOB(\"*{search.get()}*\") OR NAME GLOB(\"*{HanziConv.toSimplified(search.get())}*\") LIMIT {_start+50};").fetchall()
            if values:
                _main.add_tags_and_fresh(values[_start:_start + 50], ex=self.main_ex,
                                         fresh_event=lambda e: add_tag_50())
                num.set(_start+len(values[_start:_start+50]))
        def add_tag0group_50():
            _start = num.get()
            _key = scope.get()
            if _key == "名称":
                z = HanziConv.toSimplified(search.get())
                search.set(z)
                values = cur.execute(f"SELECT NAME, TAG0IN, TAG0IF, TAG0GROUP0IN, TAG0GROUP0IF, NOTES FROM TAG0GROUP WHERE NAME GLOB(\"*{search.get()}*\") LIMIT {_start+50};").fetchall()
            elif _key == "描述":
                values = cur.execute(f"SELECT NAME, TAG0IN, TAG0IF, TAG0GROUP0IN, TAG0GROUP0IF, NOTES FROM TAG0GROUP WHERE NOTES GLOB(\"*{search.get()}*\") LIMIT {_start+50};").fetchall()
            elif _key == "子项":
                z = HanziConv.toSimplified(search.get())
                search.set(z)
                s = "#"+search.get()+"#"
                values = cur.execute(f"SELECT NAME, TAG0IN, TAG0IF, TAG0GROUP0IN, TAG0GROUP0IF, NOTES FROM TAG0GROUP WHERE TAG0IN GLOB(\"*{s}*\") OR TAG0GROUP0IN GLOB(\"*{s}*\") LIMIT {_start+50};").fetchall()
            else:
                z = HanziConv.toSimplified(search.get())
                search.set(z)
                s = "#" + search.get() + "#"
                values = cur.execute(f"SELECT NAME, TAG0IN, TAG0IF, TAG0GROUP0IN, TAG0GROUP0IF, NOTES FROM TAG0GROUP WHERE TAG0IF GLOB(\"*{s}*\") OR TAG0GROUP0IF GLOB(\"*{s}*\") LIMIT {_start+50};").fetchall()
            if values:
                _main.add_tag0groups_and_fresh(values[_start:_start + 50], ex=self.main_ex,
                                               fresh_event=lambda e: add_tag0group_50())
                num.set(_start+len(values[_start:_start+50]))
        def _clear():
            _main.clear()
            num.set(0)
        def to_tag():
            is_tag.set(True)
            _clear()
            search.set("")
            space_["values"] = ("名称", "描述", "全部")
            scope.set("名称")
            add_tag_50()
        def to_tag0group():
            is_tag.set(False)
            _clear()
            search.set("")
            space_["values"] = ("名称", "描述", "子项", "条件")
            scope.set("名称")
            add_tag0group_50()
        def search_func():
            _clear()
            if is_tag.get():
                add_tag_50()
            else:
                add_tag0group_50()

        win_menu = tk.Menu(win)
        win["menu"] = win_menu
        but_search["command"] = search_func
        win_menu.add_command(label="TAG/刷新", command=to_tag)
        win_menu.add_command(label="TAG GROUP/刷新", command=to_tag0group)

        add_tag_50()
        win.after(500, _main.fresh_wraplength)
        win.mainloop()
        cur.close()
    def win_set_tag(self):
        if self.is_win_set_tag:
            self.set_message("不允许打开多个Tag管理窗口", "red")
            return
        else:
            self.is_win_set_tag = True

        object_tag = {
            "name": "",
            "type": -1,
            "tagIn": set(),
            "tag0groupIn": set(),
            "tagIf": set(),
            "tag0groupIf": set(),
            "note": ""
        }  # 当前操作的对象
        object_tag_copy = {}
        is_mouse_inside = tk.BooleanVar(value=False)
        is_modify = tk.BooleanVar(value=False)
        cur = self.main_ex.conn.cursor()
        # 基本架构定义
        win = tk.Toplevel(self.root)
        win.geometry(self.get_center(400, 600))
        win.title(HEAD + "--Tag管理")
        win["background"] = "#F8F8FF"
        win.wm_iconbitmap(ICO_PATH)

        message_l = tk.Label(win, text="...", style="MainBase.TLabel")
        base_f = tk.Frame(win, style="MainBase.TFrame")
        message_l.pack(side="bottom", fill="x")
        base_f.pack(side="top", fill="both", expand=True)

        choose_f = tk.Frame(base_f, style="MainBase.TFrame")
        modify_f = tk.Frame(base_f, style="MainBase.TFrame")
        choose_f.grid(column=1, row=1, sticky="nsew")
        tk.Separator(base_f, orient="horizontal").grid(row=2, column=1, sticky="nsew", pady=5)
        modify_f.grid(column=1, row=3, sticky="nsew")
        base_f.rowconfigure(3, weight=3)
        base_f.columnconfigure(1, weight=1)
        def set_message(text: str, color: str="gray") -> None:
            message_l["text"] = text
            message_l["foreground"] = color

        # 选择栏
        _is_lock = tk.BooleanVar()
        _type = tk.IntVar(value=0)  # 操作对象类型，{0: tag, 1: tag0group}
        _name = tk.StringVar(value="")

        set_type_lf = tk.Labelframe(choose_f, text="类型选择")
        set_type_r1 = tk.Radiobutton(set_type_lf, text="tag", variable=_type, value=0, style="MainBase.TRadiobutton")
        set_type_r1.grid(row=0, column=0, sticky="nsew")
        set_type_r2 = tk.Radiobutton(set_type_lf, text="tag group", variable=_type, value=1, style="MainBase.TRadiobutton")
        set_type_r2.grid(row=1, column=0, sticky="nsew")
        set_type_lf.grid(row=1, column=1, padx=10, pady=10, rowspan=4, sticky="nsew")
        tk.Label(choose_f, text="名称:", style="MainBase.TLabel").grid(row=1, column=3, padx=10, pady=10, sticky="n")
        set_name_e = tk.Entry(choose_f, textvariable=_name, width=20)
        set_name_e.grid(row=1, column=4, pady=10, sticky="n", columnspan=10)

        button1 = tk.Button(choose_f, text="取消", style="MainBase.TButton", command=None)
        button1.grid(row=2, column=13)
        button2 = tk.Button(choose_f, text="选择", style="MainBase.TButton", command=None)
        button2.grid(row=3, column=13)

        message1 = tk.Radiobutton(choose_f, text="未锁定", variable=_is_lock, value=False, style="MainBase.TRadiobutton")
        message1.state(["disabled"])
        message1.grid(row=3, column=3, sticky="nw", padx=10, columnspan=10)
        choose_f.columnconfigure(2, weight=29)
        choose_f.columnconfigure(100, weight=1)

        # 操作区
        modify_f_f1 = tk.Frame(modify_f, style="MainBase.TFrame")
        modify_f_f2 = tk.Frame(modify_f, style="MainBase.TFrame")
        modify_f_f1.place(relx=0, rely=0, relwidth=0.4, relheight=1)
        modify_f_f2.place(relx=0.4, rely=0, relwidth=0.6, relheight=1)

        modify_choose_lb = tk.Listbox(modify_f_f1, height=5, selectmode="single")
        modify_choose_lb.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        modify_choose_lb_v = [
            ["类型", "备注", "删除"],
            ["类型", "包含项", "条件项", "备注", "删除"]
        ]  # 与_type对应
        _old = tk.StringVar(value="") # 旧的选择项, ""表示无效
        def modify_choose_lb_fresh_value(*args):
            """刷新modify_choose_lb的选项"""
            _type_lb = _type.get()
            modify_choose_lb.delete(0, tk.END)
            _v = modify_choose_lb_v[_type_lb]
            for i in _v: modify_choose_lb.insert(tk.END, i)
            modify_choose_lb.selection_set(0)
            modify_choose_lb.see(0)

        to_func_b_12 = [
            [lambda:None, lambda:None], [lambda:None, lambda:None]
        ]  # 按钮1，2在两状态的钩子函数
        def to_choose():
            """调整至选择阶段"""
            is_modify.set(False)
            set_message("输入不存在的名称将进入新建模式")
            _name.set("")
            set_name_e.state(["!disabled"])
            set_type_r1.state(["!disabled"])
            set_type_r2.state(["!disabled"])
            message1["text"] = "未锁定"

            modify_choose_lb.config(state="disabled")
            if _old.get() != modify_choose_lb_v[1][4]:
                for c in modify_f_f2.children.values():
                    c.grid_forget()
            button1.config(text="取消", command=to_func_b_12[0][0])
            button1.state(["disabled"])
            button2.config(text="选择", command=to_func_b_12[0][1])
            button2.state(["!disabled"])
        def to_modify():
            """调整至修改阶段"""
            is_modify.set(True)
            set_message("点击确认键以完成更改")
            set_name_e.state(["disabled"])
            set_type_r1.state(["disabled"])
            set_type_r2.state(["disabled"])
            message1["text"] = "已锁定"

            modify_choose_lb.config(state="normal")
            modify_choose_lb_fresh_value()
            button1.config(text="取消", command=to_func_b_12[1][0])
            button1.state(["!disabled"])
            button2.config(text="确认", command=to_func_b_12[1][1])
            button2.state(["!disabled"])

            _old.set("")
            object_tag_copy["name"] = object_tag["name"]
            object_tag_copy["type"] = object_tag["type"]
            object_tag_copy["tagIn"] = object_tag["tagIn"]
            object_tag_copy["tagIf"] = object_tag["tagIf"].copy()
            object_tag_copy["tag0groupIn"] = object_tag["tag0groupIn"].copy()
            object_tag_copy["tag0groupIf"] = object_tag["tag0groupIf"].copy()
            object_tag_copy["note"] = object_tag["note"]

        # 注意，此处组件初始不绑定位置
        ## 类型
        type_lf = tk.Labelframe(modify_f_f2, text="类型")
        _tag_type_var = tk.IntVar(value=-1)
        for _r in range(len(SQL.NAME_TYPE)):
            tk.Radiobutton(type_lf, text=SQL.NAME_TYPE[_r], variable=_tag_type_var, value=_r, style="MainBase.TRadiobutton").grid(row=_r, column=0, sticky="nsew")
        ## 备注
        notes_text = tk.Text(modify_f_f2)
        ## tag相关
        tag_in_f = tk.Frame(modify_f_f2, style="TagFrame.TFrame")
        tag0group_in_f = tk.Frame(modify_f_f2, style="TagFrame.TFrame")
        tag_in = TagBox(self.root, tag_in_f, head_text="tag: ", is_id=True)
        tag0group_in = TagBox(self.root, tag0group_in_f, head_text="tag组: ", is_id=True)
        ## 删除
        del_l = tk.Label(modify_f_f2, text="是否确认删除该tag？", style="MainBase.TLabel")
        del_b = tk.Button(modify_f_f2, text="确认删除")
        del_d_l = tk.Label(modify_f_f2, text="", style="MainBase.TLabel")
        def del_tag(is_hard: bool=False):
            _n = object_tag["name"]
            _t = _type.get()
            _d = {}
            try:
                if _t == 0: # tag
                    self.main_ex.del_tag_row(_n, _d, is_hard=is_hard)
                elif _t == 1: # tag0group
                    self.main_ex.del_tag0group_row(_n, _d, is_hard=is_hard)
            except SQL.SQLDelError:
                del_l.config(text="存在关联项，最后确认，是否删除该tag？", foreground="red")
                del_b["command"] = lambda : del_tag(is_hard=True)
                _d_str = "可能的受影响项：\n"
            else:
                self.main_ex.commit()
                _d_str = "已删除\n受影响项：\n"
                to_choose()
            for k, vs in _d.items():
                for v in vs:
                    _d_str += f"\t{k}: {v}\n"
            del_d_l.config(text=_d_str)
        def del_confirm():
            del_l.config(text="再次确认，是否删除该tag？", foreground="red")
            del_b["command"] = del_tag
        def del_init():
            del_l.config(text="是否确认删除该tag？", foreground="black")
            del_b["command"] = del_confirm
            del_d_l.config(text="")

        def left_c(uid: str, is_tag: bool=True) -> typing.Callable:
            def left():
                if is_tag:
                    win_tag(win, self.main_ex, uid)
                else:
                    win_tag0group(win, self.main_ex, uid)
                set_message(f"左键查看tag，右键删除tag")
            return left
        def right_c(uid: str, box: TagBox) -> typing.Callable:
            def right(e):
                box.del_tag(uid)
                set_message(f"左键查看tag，右键删除tag")
            return right
        def modify_choose_replace():
            """根据modify_choose信息更新数据"""
            _m_old = _old.get()
            if _m_old == modify_choose_lb_v[1][0]: # 类型
                object_tag["type"] = _tag_type_var.get()
            elif _m_old == modify_choose_lb_v[1][1]: # 包含项
                object_tag["tagIn"] = set(tag_in.get_tag())
                object_tag["tag0groupIn"] = set(tag0group_in.get_tag())
            elif _m_old == modify_choose_lb_v[1][2]: # 条件项
                object_tag["tagIf"] = set(tag_in.get_tag())
                object_tag["tag0groupIf"] = set(tag0group_in.get_tag())
            elif _m_old == modify_choose_lb_v[1][3]: # 备注
                object_tag["note"] = notes_text.get("1.0", tk.END).strip()
            else:
                pass
        def modify_choose_lb_fresh(*args):
            """刷新modify_f_f2至与modify_choose_lb对应"""
            _type_lb = _type.get()
            _index_lb = modify_choose_lb.curselection()[0]
            _v = modify_choose_lb_v[_type_lb][_index_lb]
            # 更新信息
            modify_choose_replace()
            # 投放组件
            modify_f_f2.rowconfigure(0, weight=0)
            modify_f_f2.rowconfigure(1, weight=0)
            modify_f_f2.columnconfigure(0, weight=0)
            for z in modify_f_f2.winfo_children():
                z.grid_forget()
            if _v == modify_choose_lb_v[1][0]:  # 类型
                type_lf.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
                _tag_type_var.set(object_tag["type"])
                _old.set(modify_choose_lb_v[1][0])
            elif _v == modify_choose_lb_v[1][1] or _v == modify_choose_lb_v[1][2]:  # 包含项/条件项
                tag_in.clear()
                tag0group_in.clear()
                modify_f_f2.rowconfigure(0, weight=1)
                modify_f_f2.rowconfigure(1, weight=1)
                modify_f_f2.columnconfigure(0, weight=1)
                tag_in_f.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
                tag0group_in_f.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
                if _v == modify_choose_lb_v[1][1]:
                    _k = ["tagIn", "tag0groupIn"]
                    _old.set(modify_choose_lb_v[1][1])
                else:
                    _k = ["tagIf", "tag0groupIf"]
                    _old.set(modify_choose_lb_v[1][2])
                for _t in object_tag[_k[0]]:
                    tag_in.add_tag(name=_t, uid=_t,
                                   command=left_c(_t, True),
                                   right_command=right_c(_t, tag_in))
                for _t in object_tag[_k[1]]:
                    tag0group_in.add_tag(name=_t, uid=_t,
                                   command=left_c(_t, True),
                                   right_command=right_c(_t, tag0group_in))
                tag_in.fresh()
                tag0group_in.fresh()
            elif _v == modify_choose_lb_v[1][3]: # 备注
                notes_text.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
                notes_text.delete("1.0", tk.END)
                notes_text.insert(tk.END, object_tag["note"])
                _old.set(modify_choose_lb_v[1][3])
            elif _v == modify_choose_lb_v[1][4]: # 删除
                del_init()
                del_l.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
                del_b.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
                del_d_l.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
                _old.set(modify_choose_lb_v[1][4])

        modify_choose_tag_f = tk.Frame(modify_f_f1, style="MainBase.TFrame")
        modify_choose_tag_f.grid(row=1, column=0, sticky="nsew", padx=10)
        SearchTagBox(
            self.root, modify_choose_tag_f, self.main_ex,
            tag_in, tag0group_in,
            set_message=set_message
        )
        modify_f_f1.rowconfigure(1, weight=1)
        modify_f_f1.columnconfigure(0, weight=1)
        # 钩子
        def validate_name(new_char: str) -> bool:
            """验证tag名称是否合法"""
            if "#" in new_char:
                set_message("禁止在名称中使用\"#\"符")
                return False
            elif "\n" in new_char:
                button2.invoke()
                return False
            return True
        set_name_e.config(validate="key", validatecommand=(win.register(validate_name), "%S"))
        def new_tag():
            """新建tag"""
            name = object_tag["name"]
            _t = _type.get()
            if _t == 0: # tag
                self.main_ex.new_tag(name=name, notes="", _type=SQL.TYPE_TAGS)
            else: # tag0group
                self.main_ex.new_tag0group(name=name, notes="", _type=SQL.TYPE_TAGS)
            object_tag["type"] = SQL.TYPE_TAGS
            object_tag["tagIn"] = set()
            object_tag["tag0groupIn"] = set()
            object_tag["tagIf"] = set()
            object_tag["tag0groupIf"] = set()
            object_tag["note"] = ""
            to_modify()

        def choose_decide(*args):
            """判断当前_name的tag状态并进行初步操作"""
            _c_type = _type.get()
            _c_name = _name.get()
            if _c_name == "":
                return
            try:
                if _c_type == 0: # tag
                    _d = cur.execute("SELECT NAME, TYPE, NOTES FROM TAG WHERE NAME==?", (_c_name, )).fetchall()[0]
                    object_tag["name"] = _d[0]
                    object_tag["type"] = _d[1]
                    object_tag["note"] = _d[2]
                else:  # tag0group
                    _d = cur.execute("SELECT NAME, TYPE, TAG0IN, TAG0IF, TAG0GROUP0IN, TAG0GROUP0IF, NOTES FROM TAG0GROUP WHERE NAME==?", (_c_name, )).fetchall()[0]
                    object_tag["name"] = _d[0]
                    object_tag["type"] = _d[1]
                    object_tag["tagIn"] = SQL.to_r_tag(_d[2])
                    object_tag["tagIf"] = SQL.to_r_tag(_d[3])
                    object_tag["tag0groupIn"] = SQL.to_r_tag(_d[4])
                    object_tag["tag0groupIf"] = SQL.to_r_tag(_d[5])
                    object_tag["note"] = _d[6]
            except IndexError:  # tag不存在
                set_type_r1.state(["disabled"])
                set_type_r2.state(["disabled"])
                set_name_e.state(["disabled"])

                object_tag["name"] = _c_name
                button1.state(["!disabled"])
                button2.config(text="确认新建", command=new_tag)
            else:
                to_modify()
        def cancel_b_func():
            """取消操作"""
            object_tag["name"] = ""
            object_tag["type"] = -1
            object_tag["tagIn"] = set()
            object_tag["tag0groupIn"] = set()
            object_tag["tagIf"] = set()
            object_tag["tag0groupIf"] = set()
            object_tag["note"] = ""
            to_choose()
        def save_tag():
            """保存"""
            modify_choose_replace()
            _t = _type.get()
            try:
                if _t == 0: # tag
                    # 类型与备注
                    if object_tag["type"] != object_tag_copy["type"]:
                        self.main_ex.set_tag_type(name=object_tag["name"], _type=object_tag["type"])
                    if object_tag["note"] != object_tag_copy["note"]:
                        self.main_ex.write_note(_type="TAG", _key=object_tag["name"], notes=object_tag["note"])
                else: # tag0group
                    # 添加新内容，同时也是实际中唯一SQL库内置异常可能的抛出点
                    # 此处为第一项储存，故无需考虑异常导致的储存不同步
                    tag_in_new = object_tag["tagIn"] - object_tag_copy["tagIn"]
                    tag0group_in_new = object_tag["tag0groupIn"] - object_tag_copy["tag0groupIn"]
                    tag_if_new = object_tag["tagIf"] - object_tag_copy["tagIf"]
                    tag0group_if_new = object_tag["tag0groupIf"] - object_tag_copy["tag0groupIf"]
                    self.main_ex.add_tag0group(name=object_tag["name"], tag_in=tag_in_new, tag_if=tag_if_new,
                                               tag0group_in=tag0group_in_new, tag0group_if=tag0group_if_new)
                    # 删除旧内容
                    tag_in_old = object_tag_copy["tagIn"] - object_tag["tagIn"]
                    tag0group_in_old = object_tag_copy["tag0groupIn"] - object_tag["tag0groupIn"]
                    tag_if_old = object_tag_copy["tagIf"] - object_tag["tagIf"]
                    tag0group_if_old = object_tag_copy["tag0groupIf"] - object_tag["tag0groupIf"]
                    self.main_ex.del_tag0group(name=object_tag["name"],
                                               tag_in=tag_in_old, tag0group_in=tag0group_in_old,
                                               tag_if=tag_if_old, tag0group_if=tag0group_if_old)
                    # 类型与备注
                    if object_tag["type"] != object_tag_copy["type"]:
                        self.main_ex.set_tag0group_type(name=object_tag["name"], _type=object_tag["type"])
                    if object_tag["note"] != object_tag_copy["note"]:
                        self.main_ex.write_note(_type="TAG0GROUP", _key=object_tag["name"], notes=object_tag["note"])
            except SQL.SQLRecursionError as e:
                set_message(f"包含项或条件项（或其子系）中存在\'{e.goal_tag0group}\'本身，由\'{e.tag0group}\'引发", "red")
            except SQL.SQLDuplicateValuesError as e:
                set_message(f"包含项与条件项出现了重复，重复项：{e.duplicate}, 类型为{e.type}", "red")
            # except Exception as e:
            #     print(object_tag)
            #     set_message(f"未定义异常：{e}", "red")
            else:
                self.main_ex.commit()
                to_choose()

        to_func_b_12[0][0] = cancel_b_func
        to_func_b_12[0][1] = choose_decide
        to_func_b_12[1][0] = cancel_b_func
        to_func_b_12[1][1] = save_tag
        _type.trace_add("write", modify_choose_lb_fresh_value)
        modify_choose_lb.bind("<<ListboxSelect>>", modify_choose_lb_fresh)
        def on_closing():
            win.destroy()
            self.is_win_set_tag = False
        win.protocol("WM_DELETE_WINDOW", on_closing)
        win.bind("<Enter>", lambda e: is_mouse_inside.set(True))
        win.bind("<Leave>", lambda e: is_mouse_inside.set(False))
        # 快捷键
        def return_key(e):
            if is_mouse_inside.get() and not is_modify.get():
                button2.invoke()
        def up_key(e):
            if is_mouse_inside.get():
                # if is_modify.get():
                #     _this = modify_choose_lb.curselection()[0]
                #     if _this > 0:
                #         modify_choose_lb.selection_clear(_this, _this)
                #         modify_choose_lb.selection_set(_this - 1)
                # else:
                    if _type.get() == 1:
                        _type.set(0)
                    else:
                        _type.set(1)
        def down_key(e):
            if is_mouse_inside.get():
                # if is_modify.get():
                #     _this = modify_choose_lb.curselection()[0]
                #     if _this < modify_choose_lb.size() - 1:
                #         modify_choose_lb.selection_clear(_this, _this)
                #         modify_choose_lb.selection_set(_this + 1)
                # else:
                    if _type.get() == 1:
                        _type.set(0)
                    else:
                        _type.set(1)

        set_name_e.bind("<Return>", return_key)
        win.bind("<Up>", up_key)
        win.bind("<Down>", down_key)
        # 初始化
        to_choose()
        win.mainloop()
    def win_crawler(self):
        this = []
        # 基本架构定义
        win = tk.Toplevel(self.root)
        win.geometry(self.get_center(600, 400))
        win.title(HEAD + "--下载源管理")
        win["background"] = "#F8F8FF"
        win.wm_iconbitmap(ICO_PATH)

        cr_lb = tk.Listbox(win, selectmode="single", height=10)
        cr_data_f = tk.Frame(win, style="MainBase.TFrame")
        cr_lb.grid(row=0, column=0, pady=5, sticky="nsew")
        cr_data_f.grid(row=0, column=1, pady=5, sticky="nsew")
        win.rowconfigure(0, weight=1)
        win.columnconfigure(1, weight=1)

        cr_data_name_l = tk.Label(cr_data_f, style="MainBase.TLabel", text="")
        cr_data_mark_l = tk.Label(cr_data_f, style="MainBase.TLabel", text="")
        cr_data_notes_f = tk.Frame(cr_data_f, style="MainBase.TFrame")
        cr_data_note_l = tk.Label(cr_data_notes_f, style="MainBase.TLabel", text="")
        cr_data_status_l = tk.Label(cr_data_f, style="MainBase.TLabel", text="未检测", foreground="orange")
        cr_data_check_b= tk.Button(cr_data_f, text="检测连接")
        cr_data_d_e = tk.Entry(cr_data_f, style="MainBase.TEntry")
        cr_data_d_b = tk.Button(cr_data_f, text="下载", state="disabled")
        cr_data_d_message_l = tk.Label(cr_data_f, style="MainBase.TLabel", text="未开始下载", foreground="gray")

        tk.Label(cr_data_f, style="MainBase.TLabel", text="来源名：").grid(row=1, column=1, sticky="nsew", pady=5)
        cr_data_name_l.grid(row=1, column=2, sticky="nsew", pady=5)
        tk.Label(cr_data_f, style="MainBase.TLabel", text="标记符：").grid(row=2, column=1, sticky="nsew", pady=5)
        cr_data_mark_l.grid(row=2, column=2, sticky="nsew", pady=5)
        cr_data_notes_f.grid(row=4, column=1, sticky="nsew", columnspan=2, pady=5)
        tk.Label(cr_data_f, style="MainBase.TLabel", text="状态：").grid(row=9, column=1, sticky="nsew", pady=5)
        cr_data_status_l.grid(row=9, column=2, sticky="nsew", pady=5)
        cr_data_check_b.grid(row=10, column=2, sticky="nsew", pady=5)
        tk.Label(cr_data_f, style="MainBase.TLabel", text="关键字：").grid(row=11, column=1, sticky="nsew", pady=5)
        cr_data_d_e.grid(row=11, column=2, sticky="nsew", pady=5)
        cr_data_d_b.grid(row=11, column=13, sticky="nsew", pady=5)
        cr_data_d_message_l.grid(row=12, column=2, sticky="nsew")

        tk.Label(cr_data_notes_f, style="MainBase.TLabel", text="描述：").grid(row=1, column=1, sticky="nsew", pady=5)
        cr_data_note_l.grid(row=2, column=1, sticky="nsew", columnspan=2, pady=5)
        cr_data_f.rowconfigure(4, weight=1)
        _init = lambda : 0

        def w_data():
            cr = this[0]  # type:CrawlerAPI.Crawler
            zt = this[1]  # type: int
            cr_data_name_l["text"] = cr.name
            cr_data_mark_l["text"] = cr.mark
            cr_data_note_l["text"] = cr.notes
            if zt == 0:
                cr_data_status_l.config(text="未检测", foreground="orange")
            elif zt == 1:
                cr_data_status_l.config(text="正常", foreground="green")
            elif zt == 2:
                cr_data_status_l.config(text="异常", foreground="red")
            else:
                cr_data_status_l.config(text="检测中", foreground="orange")
        def selected(e):
            cr_data_d_b.config(state="!disabled")
            cr_data_d_message_l.config(text="未开始下载", foreground="gray")
            _this = cr_lb.curselection()[0]
            if _this == cr_lb.size() - 1:
                path = tk.askdirectory()
                if path:
                    CrawlerAPI.init_crawler(self.BaseCrawlerRule, path, os.path.join(THIS_PATH, "save.json"))
                    self.crawlers = CrawlerAPI.read_file_crawler(os.path.join(THIS_PATH, "save.json"), self.BaseCrawlerRule)
                    _init()
            else:
                try:
                    this[0] = self.crawlers[_this]
                    this[1] = 0
                except IndexError:
                    this.append(self.crawlers[_this])
                    this.append(0)
                w_data()
        def init():
            cr_lb.delete(0, tk.END)
            for c in self.crawlers:
                cr_lb.insert("end", c.name)
            cr_lb.insert("end", "导入源")
        def check():
            cr = this[0]  # type:CrawlerAPI.Crawler
            this[1] = -1
            w_data()
            is_s = cr.use_check()
            if is_s:
                this[1] = 1
            else:
                this[1] = 2
            w_data()
        def d():
            cr = this[0]  # type:CrawlerAPI.Crawler
            keyword = cr_data_d_e.get()
            if not keyword:
                return
            if keyword:
                cr_data_d_message_l.config(text="下载中，请勿关闭窗口", foreground="green")
                pool = ThreadPoolExecutor(max_workers=1)
                future = pool.submit(lambda x:(cr_data_d_message_l.config(text="下载完成，请在管理->暂存区访问", foreground="green")
                                               if cr.use_download_data(x) else cr_data_d_message_l.config(text="下载失败，可能是网络问题或已下载过，请在管理->暂存区访问", foreground="red")), keyword)

        cr_data_check_b["command"] = check
        cr_data_d_b["command"] = d
        cr_lb.bind("<<ListboxSelect>>", selected)
        _init = init
        init()
        win.mainloop(0)
    def win_merge(self):
        # 基本架构定义
        win = tk.Toplevel(self.root)
        win.geometry(self.get_center(300, 150))
        win.title(HEAD + "--库合并")
        win["background"] = "#F8F8FF"
        win.wm_iconbitmap(ICO_PATH)

        src = tk.StringVar()
        is_only_file = tk.BooleanVar(value=True)

        main_f = tk.Frame(win, style="MainBase.TFrame")
        main_f.place(x=0, y=0, relwidth=1, relheight=1)
        src_e = tk.Entry(main_f, textvariable=src, style="MainBase.TEntry")
        only_file_f = tk.Frame(main_f, style="MainBase.TFrame")
        only_file0_r = tk.Radiobutton(only_file_f, text="仅合并文件", variable=is_only_file, value=True, style="MainBase.TRadiobutton")
        only_file1_r = tk.Radiobutton(only_file_f, text="合并所有", variable=is_only_file, value=False, style="MainBase.TRadiobutton")
        yes_b = tk.Button(main_f, text="确认", style="MainBase.TButton")
        message_l = tk.Label(main_f, text="输入待合并的库路径", style="MainBase.TLabel", foreground="gray")

        tk.Label(main_f, text="路径：", style="MainBase.TLabel").grid(row=1, column=1, sticky="nsew", pady=5)
        src_e.grid(row=1, column=2, sticky="nsew", columnspan=3, pady=5)
        tk.Button(main_f, text="浏览", style="MainBase.TButton", command=lambda : src.set(tk.askdirectory())).grid(row=1, column=4, sticky="nsew", pady=5)
        only_file_f.grid(row=3, column=1, sticky="nsew", columnspan=4)
        yes_b.grid(row=5, column=4, sticky="nsew", pady=5, padx=5)
        message_l.grid(row=10, column=2, sticky="nsew", columnspan=3)
        main_f.rowconfigure(10, weight=1)
        main_f.columnconfigure(2, weight=1)
        only_file0_r.grid(row=3, column=2, sticky="e")
        only_file1_r.grid(row=3, column=3, sticky="e")
        only_file_f.columnconfigure(0, weight=1)

        def set_message(msg, color="gray"):
            message_l.config(text=msg, foreground=color)
        def yes_func():
            if not src.get():
                return
            elif not os.path.isdir(src.get()) or not SQL.is_explorer(src.get()):
                set_message("路径不是文件库或不存在", "red")
                return
            other = SQL.Explorer(src.get())
            set_message("合并中", "green")
            if is_only_file.get():
                self.main_ex.merge_all(other, is_only_file.get())
            else:
                self.main_ex.merge_all(other, is_only_file.get())
            set_message("合并完成", "green")
        yes_b["command"] = yes_func
        win.mainloop(0)

    def __main_homepage(self):
        main = self.root_main_homepage

        img = Image.open(os.path.join(THIS_PATH, "common/image/homepage.png")).resize(self.win_size, Image.Resampling.LANCZOS)
        img = ImageTk.PhotoImage(img)
        tk.Label(main, image=img).place(x=0, y=0, relwidth=1, relheight=1)
        self.img.append(img)

        statement_f = tk.Frame(main, style="MainBase.TFrame", borderwidth=1,
                    relief="solid")

        base_f = tk.Frame(main, style="MainBase.TFrame")
        statement_f.grid(row=1, column=1, pady=40, sticky="nsew")
        base_f.grid(row=2, column=1, pady=50, sticky="ns")
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=0)
        main.columnconfigure(2, weight=1)

        tk.Label(statement_f, text="本项目仅为学习交流使用，禁止商业用途，下载后请在24小时内删除", style="MainBase.TLabel").grid(row=0, column=0, padx=2, pady=2)
        tk.Label(statement_f, text="用户必须遵守所在地区的法律法规，不得用于非法用途，本软件不对任何人的行为负责", style="MainBase.TLabel").grid(row=1, column=0, padx=2, pady=2)
    def __main_save(self):
        main = self.root_main_save
        cur = self.main_ex.conn.cursor()
        main_top = tk.Frame(main, style="MainBase.TFrame", height=140)
        main_values = tk.Frame(main, style="MainValues.TFrame")
        separator = tk.Frame(main, height=5, cursor="sb_v_double_arrow")

        main_top.pack(side="top", fill="both")
        separator.pack(side="top", fill="x")
        main_values.pack(side="top", fill="both", expand=True)

        main_values_file_in = ListBox(self.root, main_values)
        main_top.pack_propagate(False)
        # 变量表
        key = tk.StringVar()  # 作为文件名或uid的关键词
        file_type = tk.StringVar()  # 文件类型关键词
        tag_s = tk.StringVar()  # 查找tag的临时输入
        file_s = []  # 文件id缓冲区
        num = tk.IntVar()  # 表示已输出的文件数
        num.set(0)
        is_key_name = tk.BooleanVar()  # 变量key是否被作为文件名解释
        is_key_name.set(True)

        # 上方
        s_value_f = tk.Frame(main_top, style="MainBase.TFrame")
        s_value_f.pack(side="right", fill="both")
        s_tag_f = tk.Frame(main_top, style="MainBase.TFrame")
        s_tag_f.pack(side="right", fill="both", expand=True)
        tk.Separator(main_top, orient="vertical").pack(side="right", fill="y", padx=3)
        input_f = tk.Frame(main_top, style="MainBase.TFrame")
        input_f.pack(side="right", fill="both")

        main_top.columnconfigure(10, weight=1)
        main_top.columnconfigure(20, weight=2)
        main_top.rowconfigure(0, weight=1)

        # s_value_f
        key_l = tk.Label(s_value_f, text="⇄名称：", style="MainBase.TLabel")
        key_l.grid(row=0, column=0)
        tk.Entry(s_value_f, textvariable=key, width=20).grid(row=0, column=1, columnspan=2, pady=2, padx=5, sticky="nsew")
        tk.Label(s_value_f, text="类型：", style="MainBase.TLabel", width=5).grid(row=1, column=0)
        _type_c = tk.Combobox(s_value_f, textvariable=file_type, values=SQL.NAME_FILE_TYPE, width=10)
        _type_c.grid(row=1, column=1)
        _type_c.state(["readonly"])

        tk.Label(s_value_f, style="MainBase.TLabel").grid(row=4)
        s_value_f.rowconfigure(4, weight=1)
        s_value_f.columnconfigure(1, weight=1)

        s_b1 = tk.Button(s_value_f, text="清空", command=None)
        s_b1.grid(row=5, column=2, sticky="es")
        s_b2 = tk.Button(s_value_f, text="搜索", command=None)
        s_b2.grid(row=6, column=2, sticky="es")

        # s_tag_f
        tag_f = tk.Frame(s_tag_f, style="MainBase.TFrame")
        tag_f.place(relx=0, rely=0, relwidth=0.5, relheight=1)
        tag_list_f = tk.Frame(tag_f, style="TagFrame.TFrame", borderwidth=3, relief="solid")
        tk.Label(tag_f, text="检索tag：", style="MainBase.TLabel").pack(side="top", fill="x", padx=3)
        tag_list_f.pack(side="top", fill="both", expand=True, pady=3, padx=3)

        tag0group_f = tk.Frame(s_tag_f, style="MainBase.TFrame")
        tag0group_f.place(relx=0.5, rely=0, relwidth=0.5, relheight=1)
        tag0group_list_f = tk.Frame(tag0group_f, style="TagFrame.TFrame", borderwidth=3, relief="solid")
        tk.Label(tag0group_f, text="检索tag group：", style="MainBase.TLabel").pack(side="top", fill="x", padx=3)
        tag0group_list_f.pack(side="top", fill="both", expand=True, pady=3, padx=2)

        tag_list_in = TagBox(self.root, tag_list_f, "", is_id=True)
        tag0group_list_in = TagBox(self.root, tag0group_list_f, "", is_id=True)
        # input_f
        SearchTagBox(
            self.root, input_f, self.main_ex, tag_list_in, tag0group_list_in,
            set_message=self.set_message
        )
        # 钩子
        def top_on_drag(e):
            """修改顶部搜索框大小"""
            new_height = main.winfo_pointery() - main_top.winfo_rooty()
            if new_height > 140:
                main_top.configure(height=new_height)
                main_top.update()
        # 使检索框可调整大小
        separator.bind("<B1-Motion>", top_on_drag)
        def search_file(data: list):
            """搜索file并存储至缓冲区  data:缓冲区"""
            data.clear()
            if is_key_name.get():
                _k = key.get()
            else:
                try:
                    _k = int(key.get())
                except ValueError:
                    self.set_message("请输入正确格式的uid", "red")
                    return None
            _t = file_type.get()
            _t = SQL.get_type_file_id(_t)
            if _t == -1:
                return
            [data.append(_d) for _d in self.main_ex.select_files(_k, _t,
                                                                 tag=set(tag_list_in.get_tag()),
                                                                 tag0group=set(tag0group_list_in.get_tag()),
                                                                 count_max=1000)]
        def search_file_50():
            """向main_values_file_in添加50条file"""
            _num = num.get()
            _ids = file_s[_num:_num+50]
            _d = cur.execute(f"SELECT UID, NAME, TYPE, SOURCE, TAG, TAG0GROUP, NOTES FROM FILE WHERE UID IN {SQL.SQL.to_tuple(set(_ids))}")
            main_values_file_in.add_files_and_fresh(_d, self.main_ex, fresh_event=lambda e: search_file_50())
            num.set(_num + 50)
        def clear_file():
            main_values_file_in.clear()
            file_s.clear()
            num.set(0)
        # 清空条件
        s_b1["command"] = lambda : (clear_file(), tag_list_in.clear(), tag0group_list_in.clear(), key.set(""))
        # 搜索
        s_b2["command"] = lambda : (clear_file(), search_file(file_s), search_file_50())
        # 更换key解释
        def enter(e): key_l["foreground"] = "blue"
        def leave(e): key_l["foreground"] = "black"
        def click_key(e):
            _b = is_key_name.get()
            is_key_name.set(not _b)
            if not _b:
                key_l["text"] = "⇄名称："
            else:
                key_l["text"] = "⇄编号："
        key_l.bind("<Enter>", enter)
        key_l.bind("<Leave>", leave)
        key_l.bind("<Button-1>", click_key)

        # 初始状态
        self.root.after(10, lambda: _type_c.current(SQL.TYPE_FILE_IMAGE))
    def __main_download_manage(self):
        main = self.root_main_download_manage

        # 重要变量
        file_data = {
            "uid": -1,
            "name": tk.StringVar(value="NONE"),
            "type": tk.StringVar(value=SQL.NAME_FILE_TYPE[0]),
            "notes": "",
            "source": tk.StringVar(value=""),
            "destination": tk.StringVar(value=""),
            "source_cr": ""
        }
        is_new = tk.BooleanVar(value=False)
        cur = self.main_ex.conn.cursor()
        # 底部框架
        choose_f = tk.Frame(main, style="MainBase.TFrame")
        data_f = tk.Frame(main, style="MainBase.TFrame")
        choose_f.grid(column=0, row=0, sticky="nsew")
        tk.Separator(main, orient="vertical").grid(column=1, row=0, sticky="ns", pady=3)
        data_f.grid(column=2, row=0, sticky="nsew")
        main.columnconfigure(0, minsize=200)
        main.columnconfigure(1, minsize=2)
        main.columnconfigure(2, weight=3)
        main.rowconfigure(0, weight=1)
        # data
        data_status = 0 # 0: 全不可写，1: 除地址外可写，2: 全可写
        data_uid_l = tk.Label(data_f, style="MainBase.TLabel", text=str(file_data["uid"]), foreground="red")
        data_name_e = tk.Entry(data_f, style="MainBase.TEntry", width=30, textvariable=file_data["name"])
        data_type_c = tk.Combobox(data_f, textvariable=file_data["type"], values=SQL.NAME_FILE_TYPE, width=10)
        data_source_e = tk.Entry(data_f, style="MainBase.TEntry", textvariable=file_data["source"])
        data_destination_e = tk.Entry(data_f, style="MainBase.TEntry", textvariable=file_data["destination"])

        def open_source():
            if os.path.isdir(file_data["source"].get()):
                file_data["source"].set(file_data["source"].get().replace("/", "\\", -1))
                subprocess.run(["explorer", file_data["source"].get()])
            else:
                self.set_message(f"目录\"{file_data["source"].get()}\"不存在")
        def open_destination():
            if os.path.isdir(file_data["destination"].get()):
                file_data["destination"].set(file_data["destination"].get().replace("/", "\\", -1))
                subprocess.run(["explorer", file_data["destination"].get()])
            else:
                self.set_message(f"目录\"{file_data["destination"].get()}\"不存在")
        data_source_b = tk.Button(data_f, text="打开", command=open_source)
        data_destination_b = tk.Button(data_f, text="打开", command=open_destination)

        data_tag_f = tk.Frame(data_f, style="TagFrame.TFrame")
        data_tag_in = TagBox(self.root, data_tag_f, "", is_id=True)
        data_tag0group_f = tk.Frame(data_f, style="TagFrame.TFrame")
        data_tag0group_in = TagBox(self.root, data_tag0group_f, "", is_id=True)
        data_note_t = tk.Text(data_f, height=3)
        def left_tag(name: str, is_tag: bool) -> typing.Callable:
            """打开窗口"""
            def left():
                self.set_message(f"左键点击打开详情，右键点击将此项添加至检索表/删除tag", "gray")
                if is_tag:
                    win_tag(self.root, self.main_ex, name)
                else:
                    win_tag(self.root, self.main_ex, name)
            return left
        def right_tag(name: str, is_tag: bool) -> typing.Callable:
            """删除元素"""
            def right(e):
                self.set_message(f"左键点击打开详情，右键点击将此项添加至检索表/删除tag", "gray")
                if is_tag:
                    data_tag_in.del_tag(name)
                    data_tag_in.fresh()
                else:
                    data_tag0group_in.del_tag(name)
                    data_tag0group_in.fresh()
            return right

        data_button_f = tk.Frame(data_f, style="MainBase.TFrame")

        tk.Label(data_f, style="MainBase.TLabel", text="名称：", anchor="e").grid(column=1, row=1, sticky="nsew", pady=5)
        data_name_e.grid(column=2, row=1, sticky="nsew", pady=5)
        tk.Label(data_f, style="MainBase.TLabel", text="\tuid：", anchor="e").grid(column=3, row=1, sticky="nsew", pady=5)
        data_uid_l.grid(column=4, row=1, sticky="nsew", pady=5)
        tk.Label(data_f, style="MainBase.TLabel", text="类型：", anchor="e").grid(column=1, row=2, sticky="nsew", pady=5)
        data_type_c.grid(column=2, row=2, sticky="nsew", pady=5)
        tk.Label(data_f, style="MainBase.TLabel", text="存放地址：", anchor="e").grid(column=1, row=3, sticky="nsew", pady=5)
        data_destination_e.grid(column=2, row=3, sticky="nsew", pady=5, columnspan=2)
        data_destination_b.grid(column=4, row=3, sticky="nsew", pady=5, padx=5)
        tk.Label(data_f, style="MainBase.TLabel", text="源地址：", anchor="e").grid(column=1, row=4, sticky="nsew", pady=5)
        data_source_e.grid(column=2, row=4, sticky="nsew", pady=5, columnspan=2)
        data_source_b.grid(column=4, row=4, sticky="nsew", pady=5, padx=5)
        tk.Label(data_f, style="MainBase.TLabel", text="tag：", anchor="e").grid(column=1, row=5, sticky="nsew", pady=5)
        data_tag_f.grid(column=2, row=5, sticky="nsew", pady=5, columnspan=3, rowspan=2)
        tk.Label(data_f, style="MainBase.TLabel", text="tag组：", anchor="e").grid(column=1, row=7, sticky="nsew", pady=5)
        data_tag0group_f.grid(column=2, row=7, sticky="nsew", pady=5, columnspan=3, rowspan=2)
        tk.Label(data_f, style="MainBase.TLabel", text="描述：", anchor="e").grid(column=1, row=9, sticky="nsew", pady=5)
        data_note_t.grid(column=2, row=9, sticky="nsew", pady=5, columnspan=3, rowspan=2)
        data_button_f.grid(column=1, row=11, sticky="nsew", pady=5, columnspan=100)
        data_f.columnconfigure(2, weight=4)
        data_f.columnconfigure(100, weight=1)
        data_f.rowconfigure(6, weight=1)
        data_f.rowconfigure(8, weight=1)
        data_f.rowconfigure(10, weight=1)

        data_save_b = tk.Button(data_button_f, text="保存")
        data_delete_b = tk.Button(data_button_f, text="删除")
        data_save_b.pack(side=tk.RIGHT, padx=3)
        data_delete_b.pack(side=tk.RIGHT, padx=3)

        def up_data():
            """更新显示状态"""
            if data_status == 0:
                data_uid_l.config(foreground="red")
                data_name_e.state(["disabled"])
                data_type_c.config(state="disabled")
                data_source_e.state(["disabled"])
                data_destination_e.state(["disabled"])
                data_note_t.config(state=tk.DISABLED)
                data_save_b.state(["disabled"])
                data_delete_b.state(["disabled"])
            elif data_status == 1:
                data_uid_l.config(foreground="green")
                data_name_e.config(state=tk.NORMAL)
                data_type_c.config(state="readonly")
                data_source_e.state(["disabled"])
                data_destination_e.state(["disabled"])
                data_note_t.config(state=tk.NORMAL)
                data_save_b.state(["!disabled"])
                data_delete_b.state(["!disabled"])
            elif data_status == 2:
                data_uid_l.config(foreground="green")
                data_name_e.config(state=tk.NORMAL)
                data_type_c.config(state="readonly")
                data_source_e.config(state=tk.NORMAL)
                data_destination_e.config(state=tk.NORMAL)
                data_note_t.config(state=tk.NORMAL)
                data_save_b.state(["!disabled"])
                data_delete_b.state(["!disabled"])
            data_uid_l.config(text=str(file_data["uid"]))
            data_note_t.delete("0.0", tk.END)
            data_note_t.insert(tk.END, file_data["notes"])
        def save_file():
            if data_status == 0: # 不可选状态一般用于初始无数据状态
                return
            # 同步数据
            file_data["notes"] = data_note_t.get("0.0", tk.END)
            # 保存
            if is_new.get():
                is_new.set(False)
                uid = self.main_ex.new_file(name=file_data["name"].get(),
                                            _type=SQL.get_type_file_id(file_data["type"].get()),
                                            source=file_data["source_cr"],
                                            notes=file_data["notes"])
                self.main_ex.commit()
                file_data["uid"] = uid
                self.main_ex.set_file_path(file_data["uid"], file_data["source"].get())
                file_data["destination"].set(os.path.join(self.main_ex.url_file, str(uid)))
                file_data["uid"] = uid
                self.main_ex.commit()
            else:
                self.main_ex.set_file_name(file_data["uid"], file_data["name"].get())
                self.main_ex.write_note(_key=file_data["uid"], notes=file_data["notes"], _type="FILE")

            _data = cur.execute("SELECT TAG, TAG0GROUP FROM File WHERE UID = ?", (file_data["uid"],)).fetchall()
            if not _data:
                return
            _data = _data[0]
            _ot, _otg = SQL.to_r_tag(_data[0]), SQL.to_r_tag(_data[1])
            _nt = set(data_tag_in.get_tag())
            _ntg = set(data_tag0group_in.get_tag())
            # 差异注入
            try:
                self.main_ex.add_file(file_data["uid"], _nt-_ot, _ntg-_otg)
                self.main_ex.del_file(file_data["uid"], _ot-_nt, _otg-_ntg)
            except SQL.SQLFileIfError as e:
                self.set_message("保存错误：部分tag group有前置要求，请检查", color="red")
            else:
                self.main_ex.commit()
            up_data()
        def del_file():
            nonlocal data_status
            if data_status == 0: # 不可选状态一般用于初始无数据状态
                return
            if tk.messagebox.askyesno("删除文件", f"确定删除文件{file_data['name'].get()}吗？"):
                self.main_ex.del_file_row(file_data["uid"])
                self.main_ex.commit()

                data_status = 0
            up_data()
        data_save_b.config(command=save_file)
        data_delete_b.config(command=del_file)
        up_data()
        # choose
        how_file_f = tk.Frame(choose_f, style="MainBase.TFrame")
        choose_file_f = tk.Frame(choose_f, style="MainBase.TFrame")
        choose_download_f = tk.Frame(choose_f, style="MainBase.TFrame")
        choose_tag_f = tk.Frame(choose_f, style="MainBase.TFrame")

        how_file_f.grid(column=0, row=5, sticky="nsew", pady=5)
        choose_file_f.grid(column=0, row=10, sticky="nsew", pady=8)
        tk.Separator(main).grid(column=0, row=14, sticky="ew", pady=3)
        choose_download_f.grid(column=0, row=15, sticky="nsew")
        choose_tag_f.grid(column=0, row=20, sticky="nsew")
        choose_f.rowconfigure(10, weight=1)
        choose_f.columnconfigure(0, weight=1)
        choose_f.rowconfigure(20, weight=1)
        ## how_file
        tk.Label(how_file_f, style="MainBase.TLabel", text="查询位置：").grid(column=0, row=0)
        how_file_c = tk.Combobox(how_file_f, style="MainBase.TCombobox", values=["文件uid", "下载暂存区", "文件地址"], width=10)
        how_file_c.grid(column=1, row=0)
        ## choose_file
        ### 文件uid
        choose_file_uid_l = tk.Label(choose_file_f, style="MainBase.TLabel", text="文件uid：")
        choose_file_uid_e = tk.Entry(choose_file_f, style="MainBase.TEntry", width=15)
        choose_file_uid_message_l = tk.Label(choose_file_f, style="MainBase.TLabel", text="输入uid以查询", foreground="gray")
        choose_file_uid_yes_b = tk.Button(choose_file_f, style="MainBase.TButton", text="确定")

        def choose_file_uid():
            try:
                uid = int(choose_file_uid_e.get())
            except ValueError:
                self.set_message(f"uid->{choose_file_uid_e.get()}不合法")
                return
            _data = cur.execute("SELECT NAME, TYPE, SOURCE, TAG, TAG0GROUP, NOTES FROM File WHERE UID = ?", (uid,)).fetchall()
            if not _data:
                self.set_message(f"未找到uid={uid}的文件", color="orange")
                return
            _data = _data[0]
            file_data["uid"] = int(uid)
            file_data["name"].set(_data[0])
            file_data["type"].set(SQL.NAME_FILE_TYPE[_data[1]])
            file_data["notes"] = _data[5]
            p = os.path.join(self.main_ex.url_file, str(uid)).replace("/", "\\", -1)
            file_data["destination"].set(p)
            file_data["source"].set(p)
            nonlocal data_status
            data_status = 1
            up_data()

            data_tag_in.clear()
            data_tag0group_in.clear()
            for _t in SQL.to_r_tag(_data[3]):
                data_tag_in.add_tag(name=_t,
                                    command=left_tag(_t, True), right_command=right_tag(_t, True),
                                    uid=_t)
            for _t in SQL.to_r_tag(_data[4]):
                data_tag0group_in.add_tag(name=_t,
                                          command=left_tag(_t, False), right_command=right_tag(_t, False),
                                          uid=_t)
        choose_file_uid_yes_b.config(command=choose_file_uid)
        ### 下载暂存区与文件地址
        choose_file_url = tk.StringVar()
        choose_file_url_l = tk.Label(choose_file_f, style="MainBase.TLabel", text="文件地址：")
        choose_file_url_e = tk.Entry(choose_file_f, style="MainBase.TEntry", textvariable=choose_file_url, width=15)
        choose_file_url_message_l = tk.Label(choose_file_f, style="MainBase.TLabel", text="输入文件地址以查询", foreground="gray")
        choose_file_url_b = tk.Button(choose_file_f, style="MainBase.TButton", text="确定")
        choose_file_url_b_ex = tk.Button(choose_file_f, style="MainBase.TButton", text="选择", command=lambda: choose_file_url.set(tk.askdirectory()))
        def choose_file_url_func(*args) -> None:
            p = choose_file_url.get()
            if not p:
                return
            elif not os.path.isdir(p):
                self.set_message(f"文件地址{choose_file_url.get()}不是目录", color="orange")
                return
            file_data["uid"] = -1
            file_data["name"].set("NONE")
            file_data["type"].set(SQL.NAME_FILE_TYPE[0])
            file_data["notes"] = ""
            file_data["source"].set(p)
            file_data["destination"].set("")
            file_data["source_cr"] = "本地"
            if "message.json"in os.listdir(p):
                with open(os.path.join(p, "message.json"), "r", encoding="utf-8") as f:
                    _d = json.loads(f.read())
                file_data["name"].set(_d["name"])
                file_data["notes"] = _d["notes"]
                file_data["type"].set(SQL.NAME_FILE_TYPE[int(_d["type"])])
                file_data["source_cr"] = _d["source"]

                t_win = tk.Toplevel(self.root)
                t_win.title("等待使用的tag")
                t_win.geometry("400x300")
                t_tag_f = tk.Frame(t_win, style="TagFrame.TFrame")
                t_tag_in = TagBox(t_win, t_tag_f, head_text="文件自带tag：", is_id=True, is_head=True)
                t_tag_f.grid(column=0, row=0, sticky="nsew", padx=5, pady=5)
                t_win.grid_columnconfigure(0, weight=1)
                t_win.grid_rowconfigure(0, weight=1)
                def r_tag(__n: str):
                    def r(e):
                        t = cur.execute("SELECT NAME FROM Tag WHERE NAME = ?", (__n,)).fetchall()
                        if t:
                            data_tag_in.add_tag(name=t[0][0],
                                     command=right_tag(t[0][0], True), right_command=right_tag(t[0][0], True),
                                     uid=t[0][0])
                        else:
                            if tk.messagebox.askquestion(title="确认", message=f"未找到tag={__n}，是否创建？") == "yes":
                                self.main_ex.new_tag(name=__n, _type=SQL.TYPE_TAGS, notes="")
                                self.main_ex.commit()
                                data_tag_in.add_tag(name=__n,
                                                    command=right_tag(__n, True),
                                                    right_command=right_tag(__n, True),
                                                    uid=__n)
                    return r
                for _t in _d["tags"]:
                    t_tag_in.add_tag(name=_t,
                                     command=lambda :0, right_command=r_tag(_t),
                                     uid=_t)
            nonlocal data_status
            data_status = 1
            up_data()
        choose_file_url_b.config(command=choose_file_url_func)
        def how_file_c_func(*args) -> None:
            t = how_file_c.get()
            is_new.set(not (t == "文件uid"))
            for w in choose_file_f.children.values():
                w.grid_remove()
            if t == "文件uid":
                choose_file_uid_l.grid(column=0, row=0, sticky="nsew")
                choose_file_uid_e.grid(column=1, row=0, sticky="nsew")
                choose_file_uid_message_l.grid(column=0, row=1, columnspan=2, sticky="nsew")
                choose_file_uid_yes_b.grid(column=1, row=2, sticky="e")
            elif t == "下载暂存区":
                choose_file_url_l.grid(column=0, row=0, sticky="nsew")
                choose_file_url_e.grid(column=1, row=0, sticky="nsew")
                choose_file_url_message_l.grid(column=0, row=1, columnspan=2, sticky="nsew")
                choose_file_url_b.grid(column=1, row=3, sticky="e")
                choose_file_url_b_ex.grid(column=1, row=2, sticky="e")
                choose_file_url_b_ex.config(command=lambda: choose_file_url.set(tk.askdirectory(initialdir=self.main_ex.url_scratch)))
            elif t == "文件地址":
                choose_file_url_l.grid(column=0, row=0, sticky="nsew")
                choose_file_url_e.grid(column=1, row=0, sticky="nsew")
                choose_file_url_message_l.grid(column=0, row=1, columnspan=2, sticky="nsew")
                choose_file_url_b.grid(column=1, row=3, sticky="e")
                choose_file_url_b_ex.grid(column=1, row=2, sticky="e")
                choose_file_url_b_ex.config(command=lambda: choose_file_url.set(tk.askdirectory()))
        how_file_c.bind('<<ComboboxSelected>>', how_file_c_func)
        how_file_c.current(0)
        how_file_c.state(["readonly"])
        how_file_c_func()
        ## choose_tag
        SearchTagBox(self.root, choose_tag_f, self.main_ex, data_tag_in, data_tag0group_in, set_message=self.set_message)
    def __main_output(self):
        main = self.root_main_output
        cur = self.main_ex.conn.cursor()
        pool = ThreadPoolExecutor(max_workers=1)

        choose_f = tk.Frame(main, style="MainBase.TFrame")
        data_f = tk.Frame(main, style="MainBase.TFrame")
        choose_f.grid(column=0, row=0, sticky="nsew")
        tk.Separator(main, orient="vertical").grid(column=1, row=0, sticky="ns", pady=3)
        data_f.grid(column=2, row=0, sticky="nsew")
        main.columnconfigure(0, minsize=200)
        main.columnconfigure(1, minsize=2)
        main.columnconfigure(2, weight=3)
        main.rowconfigure(0, weight=1)

        dst_url = tk.StringVar()
        mode = tk.StringVar()
        mode_choose = ["携带指定tag的文件", "指定文件与其tag", "全部tag复制", "自定义"]
        # data frame
        data_dst_e = tk.Entry(data_f, style="MainBase.TEntry", textvariable=dst_url)
        data_mode_cb = tk.Combobox(data_f, style="MainBase.TCombobox", state="readonly", textvariable=mode, values=mode_choose)
        data_lb_f = tk.Frame(data_f, style="MainBase.TFrame")
        data_yes_b = tk.Button(data_f, text="确定", style="MainBase.TButton")

        tk.Label(data_f, text="目标地址：", style="MainBase.TLabel").grid(row=1, column=1, sticky="e", pady=5)
        data_dst_e.grid(row=1, column=2, sticky="nsew", pady=5)
        tk.Button(data_f, text="选择", style="MainBase.TButton", command=lambda: dst_url.set(tk.askdirectory())).grid(row=1, column=3, sticky="e", pady=5, padx=5)
        tk.Label(data_f, text="模式：", style="MainBase.TLabel").grid(row=2, column=1, sticky="e", pady=5)
        data_mode_cb.grid(row=2, column=2, sticky="nsew", pady=5)
        data_lb_f.grid(row=3, column=1, sticky="nsew", pady=5, columnspan=3)
        data_yes_b.grid(row=51, column=3, sticky="e", pady=20, padx=10)
        data_f.columnconfigure(2, weight=1)
        data_f.rowconfigure(3, weight=1)
        data_f.rowconfigure(50, weight=2)

        data_file_lb = tk.Listbox(data_lb_f, selectmode="extended", state="disabled")
        context_file_menu = tk.Menu(main, tearoff=0)
        data_tag_lb = tk.Listbox(data_lb_f, selectmode="extended", state="disabled")
        context_tag_menu = tk.Menu(main, tearoff=0)
        data_tag0group_lb = tk.Listbox(data_lb_f, selectmode="extended", state="disabled")
        context_tag0group_menu = tk.Menu(main, tearoff=0)

        data_0l = tk.Label(data_lb_f, text="文件：", style="MainBase.TLabel")
        data_1l = tk.Label(data_lb_f, text="tag：", style="MainBase.TLabel")
        data_2l = tk.Label(data_lb_f, text="tag组：", style="MainBase.TLabel")
        data_0l.grid(row=2, column=1, sticky="w", padx=10)
        data_file_lb.grid(row=3, column=1, sticky="nsew", pady=5, padx=5)
        data_1l.grid(row=2, column=2, sticky="w", padx=10)
        data_tag_lb.grid(row=3, column=2, sticky="nsew", pady=5, padx=5)
        data_2l.grid(row=2, column=3, sticky="w", padx=10)
        data_tag0group_lb.grid(row=3, column=3, sticky="nsew", pady=5, padx=5)
        data_lb_f.columnconfigure(1, weight=1)
        data_lb_f.columnconfigure(2, weight=1)
        data_lb_f.columnconfigure(3, weight=1)
        data_lb_f.rowconfigure(3, weight=1)

        # choose frame
        file_f = tk.Frame(choose_f, style="MainBase.TFrame")
        tags_f = tk.Frame(choose_f, style="MainBase.TFrame")
        file_f.grid(row=1, column=1, sticky="nsew", pady=20)
        tags_f.grid(row=2, column=1, sticky="nsew")
        choose_f.rowconfigure(0, weight=3)
        choose_f.rowconfigure(1, weight=1)
        choose_f.rowconfigure(2, weight=2)
        file_sb = SearchBoxToTkListbox(self.root, file_f, self.main_ex, "file", [data_file_lb], "文件名：", self.set_message)
        tags_sb = SearchBoxToTkListbox(self.root, tags_f, self.main_ex, "tag", [data_tag_lb, data_tag0group_lb], "tag：", self.set_message)
        file_sb.set_write(False)
        tags_sb.set_write(False)
        # 钩子
        def mode_change(*args):
            _m = mode.get()
            data_file_lb.delete(0, tk.END)
            data_tag_lb.delete(0, tk.END)
            data_tag0group_lb.delete(0, tk.END)
            for z in data_lb_f.children.values():
                z.grid_forget()
            if _m == mode_choose[0]:
                data_1l.grid(row=2, column=1, sticky="w", padx=10)
                data_tag_lb.grid(row=3, column=1, sticky="nsew", pady=5, padx=5)
                data_2l.grid(row=2, column=2, sticky="w", padx=10)
                data_tag0group_lb.grid(row=3, column=2, sticky="nsew", pady=5, padx=5)
                data_file_lb.configure(state="disabled")
                data_tag_lb.configure(state="normal")
                data_tag0group_lb.configure(state="normal")
                file_sb.set_write(False)
                tags_sb.set_write(True)
            elif _m == mode_choose[1]:
                data_0l.grid(row=2, column=1, sticky="w", padx=10)
                data_file_lb.grid(row=3, column=1, sticky="nsew", pady=5, padx=5)
                data_file_lb.configure(state="normal")
                data_tag_lb.configure(state="disabled")
                data_tag0group_lb.configure(state="disabled")
                file_sb.set_write(True)
                tags_sb.set_write(False)
            elif _m == mode_choose[2]:
                data_file_lb.configure(state="disabled")
                data_tag_lb.configure(state="disabled")
                data_tag0group_lb.configure(state="disabled")
                file_sb.set_write(False)
                tags_sb.set_write(False)
            else:
                data_0l.grid(row=2, column=1, sticky="w", padx=10)
                data_file_lb.grid(row=3, column=1, sticky="nsew", pady=5, padx=5)
                data_1l.grid(row=2, column=2, sticky="w", padx=10)
                data_tag_lb.grid(row=3, column=2, sticky="nsew", pady=5, padx=5)
                data_2l.grid(row=2, column=3, sticky="w", padx=10)
                data_tag0group_lb.grid(row=3, column=3, sticky="nsew", pady=5, padx=5)
                data_file_lb.configure(state="normal")
                data_tag_lb.configure(state="normal")
                data_tag0group_lb.configure(state="normal")
                file_sb.set_write(True)
                tags_sb.set_write(True)
        mode.trace_add("write", mode_change)
        def yes_func():
            _url = dst_url.get()
            if not _url or not os.path.isdir(_url):
                self.set_message(f"地址\"{_url}\"不存在", "red")
                return
            _m = mode.get()
            self.set_message(f"分离至\"{_url}\"中，请勿关闭窗口", "green")
            if _m == mode_choose[0]:
                self.main_ex.split_file_if_tag(_url, set(data_tag_lb.get(0, tk.END)), set(data_tag0group_lb.get(0, tk.END)))
            elif _m == mode_choose[1]:
                _file = data_file_lb.get(0, tk.END)
                _f = set()
                for _n in _file:
                    _f.add(int(_n[:_n.index(":")]))
                self.main_ex.split_file_and_tag(_url, _f)
            elif _m == mode_choose[2]:
                self.main_ex.split_all_tag(_url)
            else:
                _file = data_file_lb.get(0, tk.END)
                _f = set()
                for _n in _file:
                    _f.add(int(_n[:_n.index(":")]))
                self.main_ex.split_customize(_url, set(data_tag_lb.get(0, tk.END)), set(data_tag0group_lb.get(0, tk.END)), _f)
            self.set_message(f"分离完成", "green")
        data_yes_b["command"] = lambda :pool.submit(yes_func)
        def menu_func(menu: tk.Menu) -> typing.Callable[[tk.Event], None]:
            def show_menu(e: tk.Event):
                menu.post(e.x_root, e.y_root)
            return show_menu
        data_file_lb.bind("<Button-3>", menu_func(context_file_menu))
        data_tag_lb.bind("<Button-3>", menu_func(context_tag_menu))
        data_tag0group_lb.bind("<Button-3>", menu_func(context_tag0group_menu))
        context_file_menu.add_command(label="删除", command=lambda :[data_file_lb.delete(i) for i in data_file_lb.curselection()[-1::-1]])
        context_tag_menu.add_command(label="删除", command=lambda :[data_tag_lb.delete(i) for i in data_tag_lb.curselection()[-1::-1]])
        context_tag0group_menu.add_command(label="删除", command=lambda :[data_tag0group_lb.delete(i) for i in data_tag0group_lb.curselection()[-1::-1]])
        context_file_menu.add_command(label="清除全部", command=lambda : data_file_lb.delete(0, tk.END))
        context_tag_menu.add_command(label="清除全部", command=lambda : data_tag_lb.delete(0, tk.END))
        context_tag0group_menu.add_command(label="清除全部", command=lambda : data_tag0group_lb.delete(0, tk.END))

    def run(self):
        self.root.mainloop()

    def __del__(self):
        try:
            del self.main_ex
            with open(os.path.join(THIS_PATH, "save.json"), "w", encoding="utf-8") as f:
                f.write(json.dumps(self.json))
        except:
            pass

    @staticmethod
    def get_center(w: int, h: int) -> str:
        """返回对应中心点的窗口"""
        c = SCREEN_W >> 1, SCREEN_H >> 1, w >> 1, h >> 1
        return f"{w}x{h}+{c[0] - c[2]}+{c[1] - c[3]}"

if __name__ == "__main__":
    a = GUI((800, 600))
    a.run()
