# coding=utf-8
"""
用于进行文件及相关SQL的管理
注意：繁体中文名称（tag name字段，file name字段等）将被更改为简体中文

无视：此类文件可能在统计或类似处理中无法识别，不会对文件数据产生影响
对于以图片，漫画为主的文件，满足：
    使用TYPE_FILE_IMAGE为type
    文件规范：
        [size]: %05d 编号
        以"[size]"标记根目录下的每一个文件夹，不可重复
        以"[size]"标记文件，不允许多层文件夹嵌套
        将以[size] == 00000的为封面：如果是文件，直接使用；如果是文件夹，使用其子文件[size] == 00000
        不符合要求的文件将会被无视，编号必须连续
对于以文本，小说为主的文件，满足：
    使用TYPE_FILE_TEXT为type
    文件规范：
        不符合要求的文件将会被无视，编号必须连续
        主文件夹下名称为"cover"(不含扩展名)被视为封面
对于以游戏为主的文件，满足：
    使用TYPE_FILE_GAME为type
    文件规范：
        不符合要求的文件将会被无视，编号必须连续
        主文件夹下名称为"cover"(不含扩展名)被视为封面
对于以视频为主的文件，满足：
    使用TYPE_FILE_VIDED为type
    文件规范：
        不符合要求的文件将会被无视，编号必须连续
        主文件夹下名称为"cover"(不含扩展名)被视为封面
"""
import os
import typing
from os.path import join, isdir, isfile
import shutil
from hanziconv import HanziConv
import sqlite3

class SQLError(Exception):
    """SQL相关错误的基类"""
    pass
class SQLNewKeyError(SQLError):
    """表示SQL某项关键字命名发生冲突或名称不符合规范（如含有'#'）
        key 表示冲突的值
        type 发生冲突的表名
    """
    def __init__(self, key: str|int, _type: str):
        self.key = key
        self.type = _type
class SQLNULLError(SQLError):
    """表示请求的数据中，key字为指定值的对应表中不存在该数据列
        key 关键字
        type 表名
    """
    def __init__(self, key: str|int, _type: str):
        self.key = key
        self.type = _type
class SQLDelError(SQLError):
    """表示在删除时，发现其存在依赖项且未指定hard"""
    def __init__(self):
        pass
class SQLValueTagError(SQLError):
    """表示tag或tag0group存在但在所查询的数据项中不含此
        key 表示错误的值
        type 发生错误值的表名
    """
    def __init__(self, key: str|int, _type: str):
        self.key = key
        self.type = _type
class SQLRecursionError(SQLError):
    """表示在tag0group的修改后，相关值可能发生自递归
        如tag0group_in包含其本身、tag0group_if中的一项需要以其本身为tag0group_if
        goal_tag0group：试图更改的group
        tag0group：引发自递归的group，它可能是某个group_if的group_if，因此有时并不直观
    """
    def __init__(self, goal_tag0group: str, tag0group: str):
        self.goal_tag0group = goal_tag0group
        self.tag0group = tag0group
class SQLDuplicateValuesError(SQLError):
    """表示在更改时，发生了重复的输入或使得tag0group的in项与if项发生重复
        duplicate：关键字
        type：表名
    """
    def __init__(self, duplicate: str, _type: str):
        self.duplicate = duplicate
        self.type = _type
class SQLFileIfError(SQLError):
    """表示在设置文件tag与tag0group时，不满足其if条件
    """
    def __init__(self):
        pass

# tag类型
NAME_TYPE = ("特点", "艺术家", "角色", "作品")
TYPE_TAGS = 0  # 一切其余标签，或可称作TYPE_OTHER?
TYPE_WRITER = 1  # 作者，艺术家
TYPE_ACTOR = 2  # 角色
TYPE_WORKS = 3  # 来自作品

URL_SQL = r"data.db"  # 数据库文件名
URL_FILE_DIR = r"save"  # 保存文件目录
URL_FILE_SCRATCH_DIR = r"scratch"  # 临时文件目录，在URL_FILE_DIR下

def to_simple_zh(par_str: list[str]=(), par_list: list[str]=(), par_set: list[str]=()) -> typing.Callable:
    """
    修饰器，将指定参数的繁体改为简体
    :param par_str: 类型为str的par名，特别的，如果传入非str值将被省略
    :param par_list: 类型为list[str]的par名
    :param par_set: 类型为set[str]的par名
    """
    import inspect
    from functools import wraps
    def decorator(func):
        sig = inspect.signature(func)
        @wraps(func)
        def wrapper(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            for _par in par_str:
                if not isinstance(bound.arguments[_par], str):
                    continue
                if _par in bound.arguments.keys():
                    bound.arguments[_par] = HanziConv.toSimplified(bound.arguments[_par])
            for _par in par_list:
                if _par in bound.arguments.keys():
                    bound.arguments[_par] = [HanziConv.toSimplified(_text) for _text in bound.arguments[_par]]
            for _par in par_set:
                if _par in bound.arguments.keys():
                    bound.arguments[_par] = {HanziConv.toSimplified(_text) for _text in bound.arguments[_par]}
            return func(*bound.args, **bound.kwargs)
        return wrapper
    return decorator

class SQL:
    """
    为该程序提供以sqlite为基础的数据库管理\n
    对于所有添加、更改操作，须通过内置方法进行\n
    tag, tag0group的添加、更改内置方法不支持多线程，这是为了防止可能的数据同步性问题\n
    对于查询，除内置的查询方法外，请调用self.conn创建新指针
    """
    data = {
        "TABLE": {
            "DATA": ["NAME BLOB PRIMARY KEY NOT NULL",
                     "VALUE BLOB NOT NULL"],
            "TAG": ["NAME TEXT PRIMARY KEY NOT NULL",
                    "TYPE INT NOT NULL",
                    "IN0GROUP TEXT",
                    "NOTES TEXT"],
            "TAG0GROUP": ["NAME TEXT PRIMARY KEY NOT NULL",
                          "TYPE INT NOT NULL",
                          "TAG0IN TEXT",
                          "TAG0IF TEXT",
                          "TAG0GROUP0IN TEXT",
                          "TAG0GROUP0IF TEXT",
                          "IN0GROUP TEXT",
                          "NOTES TEXT"],
            "FILE": ["UID INT PRIMARY KEY NOT NULL",
                     "NAME TEXT NOT NULL",
                     "TYPE INT NIT NULL",
                     "SOURCE TEXT NOT NULL",
                     "TAG TEXT",
                     "TAG0GROUP TEXT",
                     "NOTES TEXT"]
        }
    }
    def __init__(self, url: str, is_new: bool=False):
        """
        :param url: 数据库文件名
        :param is_new: 是否新建数据库
        """
        self.url = url
        self.conn = sqlite3.connect(url)
        self.cur = self.conn.cursor()
        if is_new:
            self.create()

    def create(self) -> bool:
        """新建库"""
        for n, v in self.data["TABLE"].items():
            text = f"CREATE TABLE {n}("+",".join(v)+");"
            self.cur.execute(text)
        self.cur.execute(f"INSERT INTO DATA VALUES (\"file_num\", 0);")
        self.cur.execute(f"CREATE INDEX FILE_NAME ON FILE(NAME);")
        self.conn.commit()
        return True

    def __request_num(self, _type: str) -> int:
        """
        申请一个uid
        :param _type: 申请类型，暂时只支持文件
        :return: 申请到的uid
        """
        num = self.cur.execute(f"SELECT VALUE FROM DATA WHERE NAME == \"{_type}\";").fetchall()[0][0]
        self.cur.execute(f"UPDATE DATA SET VALUE = VALUE+1 WHERE NAME == \"{_type}\";")
        return num

    def __set_in0group(self, names: set[str], value: str, is_tag: bool=True):
        """
        修改指定name的in0group，注意：它没有数据检查
        :param names: 要修改的列的NAME
        :param value: 要添加的in0group
        :param is_tag: 是否为tag，否则为tag0group
        :return: 是否修改成功
        """
        names = SQL.to_tuple(names)
        if is_tag:
            old_in = self.cur.execute(f"SELECT NAME, IN0GROUP FROM TAG WHERE NAME IN {names};").fetchall()
            for _name, _in in old_in:
                _in = to_r_tag(_in)
                _in.add(value)
                _in = SQL.__to_w_tag(_in)
                self.cur.execute("UPDATE TAG SET IN0GROUP = ? WHERE NAME == ?;", (_in, _name))
        else:
            old_in = self.cur.execute(f"SELECT NAME, IN0GROUP FROM TAG0GROUP WHERE NAME IN {names};").fetchall()
            for _name, _in in old_in:
                _in = to_r_tag(_in)
                _in.add(value)
                _in = SQL.__to_w_tag(_in)
                self.cur.execute("UPDATE TAG0GROUP SET IN0GROUP = ? WHERE NAME == ?;", (_in, _name))
        return True
    def __del_in0group(self, name: str, tag: set[str], tag0group: set[str]) -> bool:
        """
        清除in0group，注意：它没有数据检查
        :param name: 要清除的in0group
        :param tag: 要清除的tag列的NAME
        :param tag0group: 要清除的tag0group列的NAME
        :return: 是否清除成功
        """
        tag = SQL.to_tuple(tag)
        tag0group = SQL.to_tuple(tag0group)
        old_in = self.cur.execute(f"SELECT NAME, IN0GROUP FROM TAG WHERE NAME IN {tag};").fetchall()
        for _name, _in in old_in:
            _in = to_r_tag(_in)
            _in.remove(name)
            _in = SQL.__to_w_tag(_in)
            self.cur.execute("UPDATE TAG SET IN0GROUP = ? WHERE NAME == ?;", (_in, _name))
        old_in = self.cur.execute(f"SELECT NAME, IN0GROUP FROM TAG0GROUP WHERE NAME IN {tag0group};").fetchall()
        for _name, _in in old_in:
            _in = to_r_tag(_in)
            _in.remove(name)
            _in = SQL.__to_w_tag(_in)
            self.cur.execute("UPDATE TAG0GROUP SET IN0GROUP = ? WHERE NAME == ?;", (_in, _name))
        return True

    @to_simple_zh(par_str=["name"])
    def new_tag(self, name: str, notes: str, _type: int) -> bool:
        """
        添加一个tag列
        :param name:名称，唯一key， 不能包含#
        :param notes: 备注
        :param _type: 类型，参考常量
        :return: 是否添加成功
        """
        if self.exist("TAG", name, self.cur) or "#" in name:
            raise SQLNewKeyError(name, "TAG")
        text = "INSERT INTO TAG (NAME, IN0GROUP, NOTES, TYPE) VALUES (?, ?, ?, ?);"
        self.cur.execute(text, (name, "#", notes, _type))
        return True
    @to_simple_zh(par_str=["name"])
    def set_tag_type(self, name: str, _type: int) -> bool:
        """
        修改指定name的tag的type
        :param name: 要修改的tag的NAME
        :param _type: 要修改的类型
        :return: 是否修改成功
        """
        if not self.exist("TAG", name, self.cur):
            raise SQLNULLError(name, "TAG")
        text = f"UPDATE TAG SET TYPE = ? WHERE NAME == ?;"
        self.cur.execute(text, (_type, name))
        return True
    @to_simple_zh(par_str=["name"])
    def del_tag_row(self, name: str, _data: dict[str:set[str]], is_hard: bool=False) -> bool:
        """
        删除指定name的tag列
        :param name: 要删除的tag的NAME
        :param _data: 返回受影响的列，包括TAG0IN, TAG0IF, FILE，无论是否强制删除
        :param is_hard: 是否强制删除，否则会检查是否有文件或tag引用该tag
        :return: 是否删除成功
        """
        if not self.exist("TAG", name, self.cur):
            raise SQLNULLError(name, "TAG")
        _data["TAG0IN"] = self.cur.execute(f"SELECT NAME, TAG0IN FROM TAG0GROUP WHERE TAG0IN GLOB(\"*{name}*\");").fetchall()
        _data["TAG0IF"] = self.cur.execute(f"SELECT NAME, TAG0IF FROM TAG0GROUP WHERE TAG0IF GLOB(\"*{name}*\");").fetchall()
        _data["FILE"] = self.cur.execute(f"SELECT UID, TAG FROM FILE WHERE TAG GLOB(\"*{name}*\");").fetchall()
        if _data["TAG0IN"] or _data["TAG0IF"] or _data["FILE"]:
            if not is_hard:
                raise SQLDelError()
            text = "UPDATE TAG0GROUP SET TAG0IN = ? WHERE NAME == ?;"
            for _k, _t in _data["TAG0IN"]:
                _t = to_r_tag(_t)
                _t.remove(name)
                self.cur.execute(text, (self.__to_w_tag(_t), _k))
            text = "UPDATE TAG0GROUP SET TAG0IF = ? WHERE NAME == ?;"
            for _k, _t in _data["TAG0IF"]:
                _t = to_r_tag(_t)
                _t.remove(name)
                self.cur.execute(text, (self.__to_w_tag(_t), _k))
            text = "UPDATE FILE SET TAG = ? WHERE UID == ?;"
            for _k, _t in _data["FILE"]:
                _t = to_r_tag(_t)
                _t.remove(name)
                self.cur.execute(text, (self.__to_w_tag(_t), _k))
        text = "DELETE FROM TAG WHERE NAME == ?;"
        self.cur.execute(text, (name,))
        return True

    @to_simple_zh(par_str=["name"])
    def new_tag0group(self, name: str, notes: str, _type: int) -> bool:
        """
        添加一个tag0group列
        :param name: 名称，唯一key， 不能包含#
        :param notes: 备注
        :param _type: 类型，参考常量
        :return: 是否添加成功
        """
        if self.exist("TAG0GROUP", name, self.cur) or "#" in name:
            raise SQLNewKeyError(name, "TAG0GROUP")
        text1 = "INSERT INTO TAG0GROUP (NAME, TAG0IN, TAG0IF, TAG0GROUP0IN, TAG0GROUP0IF, IN0GROUP, NOTES, TYPE) VALUES (?, \"#\", \"#\", \"#\", \"#\", \"#\", ?, ?);"
        self.cur.execute(text1, (name, notes, _type))
        return True
    @to_simple_zh(par_str=["name"])
    def set_tag0group_type(self, name: str, _type: int) -> bool:
        """
        修改指定name的tag0group的type
        :param name: 要修改的tag0group的NAME
        :param _type: 要修改的类型
        :return: 是否修改成功
        """
        if not self.exist("TAG0GROUP", name, self.cur):
            raise SQLNULLError(name, "TAG0GROUP")
        text = f"UPDATE TAG0GROUP SET TYPE = ? WHERE NAME == ?;"
        self.cur.execute(text, (_type, name))
        return True
    @to_simple_zh(par_str=["name"], par_set=["tag_in", "tag_if", "tag0group_in", "tag0group_if"])
    def add_tag0group(self, name: str, tag_in: set[str], tag_if: set[str], tag0group_in: set[str], tag0group_if: set[str]) -> bool:
        """
        为tag0group添加子系与条件，注意：重复，子系递归后可能包含自己等会导致失败
        :param name: 要修改的tag0group的NAME
        :param tag_in: 要添加的tag的NAME，注意：重复项会被自动去重
        :param tag_if: 要添加的tag的NAME，注意：重复项会被自动去重
        :param tag0group_in: 要添加的tag0group的NAME，注意：重复项会被自动去重
        :param tag0group_if: 要添加的tag0group的NAME，注意：重复项会被自动去重
        :return: 是否修改成功
        """
        self.exists_error(self.cur, tag_in.union(tag_if), tag0group_in.union(tag0group_if, {name}))
        # 自递归
        if name in tag0group_if or name in tag0group_in:
            raise SQLRecursionError(name, name)
        else:
            self.__ok_tag0group_recursion(name, tag0group_in)
            self.__ok_tag0group_recursion(name, tag0group_if)
        _all = (set(), set(), set(), set())
        [(_all[0].update(to_r_tag(_tg[0])), _all[1].update(to_r_tag(_tg[1])), _all[2].update(to_r_tag(_tg[2])), _all[3].update(to_r_tag(_tg[3])) )
         for _tg in self.cur.execute("SELECT TAG0IN, TAG0IF, TAG0GROUP0IN, TAG0GROUP0IF FROM TAG0GROUP WHERE NAME = ? LIMIT 1;", (name, )).fetchall()]
        # 新旧出现重复项
        _is = not tag_in.isdisjoint(_all[0]), not tag_if.isdisjoint(_all[1]), not tag0group_in.isdisjoint(_all[2]), not tag0group_if.isdisjoint(_all[3])
        if _is[0] or _is[1] or _is[2] or _is[3]:
            if _is[0]:
                _v = tag_in.intersection(_all[0]).pop()
                _type = "TAG"
            elif _is[1]:
                _v = tag_if.intersection(_all[1]).pop()
                _type = "TAG"
            elif _is[2]:
                _v = tag0group_in.intersection(_all[2]).pop()
                _type = "TAG0GROUP"
            else:
                _v = tag0group_if.intersection(_all[3]).pop()
                _type = "TAG0GROUP"
            raise SQLDuplicateValuesError(_v, _type)
        # if与in分项重复
        (_all[0].update(tag_in), _all[1].update(tag_if), _all[2].update(tag0group_in), _all[3].update(tag0group_if))
        _is = not _all[0].isdisjoint(_all[1]), not _all[2].isdisjoint(_all[3])
        if _is[0] or _is[1]:
            if _is[0]:
                _v = _all[0].intersection(_all[1]).pop()
                _type = "TAG"
            else:
                _v = _all[2].intersection(_all[3]).pop()
                _type = "TAG0GROUP"
            raise SQLDuplicateValuesError(_v, _type)

        self.__set_in0group(names=tag_in, value=name, is_tag=True)
        self.__set_in0group(names=tag0group_in, value=name, is_tag=False)
        # 确保其始终是完全有序
        tag_in = self.__to_w_tag(_all[0])
        tag_if = self.__to_w_tag(_all[1])
        tag0group_in = self.__to_w_tag(_all[2])
        tag0group_if = self.__to_w_tag(_all[3])

        text = "UPDATE TAG0GROUP SET TAG0IN = ?, TAG0IF = ?, TAG0GROUP0IN = ?, TAG0GROUP0IF = ? WHERE (NAME == ?);"
        self.cur.execute(text, (tag_in, tag_if, tag0group_in, tag0group_if, name))
        return True
    @to_simple_zh(par_str=["name"], par_set=["tag_in", "tag_if", "tag0group_in", "tag0group_if"])
    def del_tag0group(self, name: str, tag_in: set[str], tag_if: set[str], tag0group_in: set[str], tag0group_if: set[str]) -> bool:
        """
        为tag0group删除子系与条件，注意：传入非已包含子系与条件名称将导致失败
        :param name: 要修改的tag0group的NAME
        :param tag_in: 要删除的tag的NAME，注意：重复项会被自动去重
        :param tag_if: 要删除的tag的NAME，注意：重复项会被自动去重
        :param tag0group_in: 要删除的tag0group的NAME，注意：重复项会被自动去重
        :param tag0group_if: 要删除的tag0group的NAME，注意：重复项会被自动去重
        :return: 是否修改成功
        """
        self.exists_error(self.cur, tag_in.union(tag_if), tag0group_in.union(tag0group_if, {name}))

        _data = [to_r_tag(i) for i in self.cur.execute("SELECT TAG0IN, TAG0IF, TAG0GROUP0IN, TAG0GROUP0IF FROM TAG0GROUP WHERE NAME == ? LIMIT 1;", (name,)).fetchall()[0]]
        if not tag_in.issubset(_data[0]):
            raise SQLValueTagError(tag_in.symmetric_difference(_data[0]).pop(), "TAG")
        elif not tag_if.issubset(_data[1]):
            raise SQLValueTagError(tag_if.symmetric_difference(_data[1]).pop(), "TAG")
        elif not tag0group_in.issubset(_data[2]):
            raise SQLValueTagError(tag0group_in.symmetric_difference(_data[2]).pop(), "TAG0GROUP")
        elif not tag0group_if.issubset(_data[3]):
            raise SQLValueTagError(tag0group_if.symmetric_difference(_data[3]).pop(), "TAG0GROUP")

        self.__del_in0group(name, tag_in, tag0group_in)
        for _d, _i in ((tag_in, 0), (tag_if, 1), (tag0group_in, 2), (tag0group_if, 3)):
            _data[_i].symmetric_difference_update(_d)
        text = "UPDATE TAG0GROUP SET TAG0IN = ?, TAG0IF = ?, TAG0GROUP0IN = ?, TAG0GROUP0IF = ? WHERE NAME == ?;"
        self.cur.execute(text, (
        self.__to_w_tag(_data[0]), self.__to_w_tag(_data[1]), self.__to_w_tag(_data[2]), self.__to_w_tag(
            _data[3]), name))
        return True
    @to_simple_zh(par_str=["name"])
    def del_tag0group_row(self, name: str, _data: dict[str:], is_hard: bool=False) -> bool:
        """
        删除tag0group列
        :param name: 要删除的tag0group的NAME
        :param _data: 获取受影响的列，包括TAG0IN, TAG0IF, FILE，无论是否强制删除
        :param is_hard: 是否强制删除，注意：强制删除将删除所有包含该tag0group的子项
        :return: 是否删除成功
        """
        if not self.exist("TAG0GROUP", name, self.cur):
            raise SQLNULLError(name, "TAG0GROUP")
        _data["TAG0GROUP0IN"] = self.cur.execute(f"SELECT NAME, TAG0GROUP0IN FROM TAG0GROUP WHERE TAG0GROUP0IN GLOB(\"*{name}*\");").fetchall()
        _data["TAG0GROUP0IF"] = self.cur.execute(f"SELECT NAME, TAG0GROUP0IF FROM TAG0GROUP WHERE TAG0GROUP0IF GLOB(\"*{name}*\");").fetchall()
        _data["FILE"] = self.cur.execute(f"SELECT UID, TAG0GROUP FROM FILE WHERE TAG0GROUP GLOB(\"*{name}*\");").fetchall()
        if _data["TAG0GROUP0IN"] or _data["TAG0GROUP0IF"] or _data["FILE"]:
            if not is_hard:
                raise SQLDelError()
            text = "UPDATE TAG0GROUP SET TAG0GROUP0IN = ? WHERE NAME == ?;"
            for _k, _t in _data["TAG0GROUP0IN"]:
                _t = to_r_tag(_t)
                _t.remove(name)
                self.cur.execute(text, (self.__to_w_tag(_t), _k))
            text = "UPDATE TAG0GROUP SET TAG0GROUP0IF = ? WHERE NAME == ?;"
            for _k, _t in _data["TAG0GROUP0IF"]:
                _t = to_r_tag(_t)
                _t.remove(name)
                self.cur.execute(text, (self.__to_w_tag(_t), _k))
            text = "UPDATE FILE SET TAG0GROUP = ? WHERE UID == ?;"
            for _k, _t in _data["FILE"]:
                _t = to_r_tag(_t)
                _t.remove(name)
                self.cur.execute(text, (self.__to_w_tag(_t), _k))
        _tin, _tgin = (to_r_tag(_d) for _d in self.cur.execute("SELECT TAG0IN, TAG0GROUP0IN FROM TAG0GROUP WHERE NAME == ?;", (name,)).fetchall()[0])
        self.__del_in0group(name, _tin, _tgin)
        text = "DELETE FROM TAG0GROUP WHERE NAME == ?;"
        self.cur.execute(text, (name,))
        return True

    @to_simple_zh(par_str=["name"])
    def new_file(self, name: str, _type: int, source: str="local", notes: str="无描述") -> int:
        """
        添加文件
        :param name: 文件名称
        :param _type: 文件类型，参考常量
        :param source: 文件来源，默认local(本地)
        :param notes: 文件描述，默认无描述
        :return: 是否添加成功
        """
        cur = self.conn.cursor()
        text = "INSERT INTO FILE (UID, NAME, TYPE, SOURCE, TAG, TAG0GROUP, NOTES) VALUES (?, ?, ?, ?, \"#\", \"#\", ?);"
        new_uid = self.__request_num("file_num")
        cur.execute(text, (new_uid, name, _type, source, notes))
        cur.close()
        return new_uid
    @to_simple_zh(par_set=["tag", "tag0group"])
    def add_file(self, uid: int, tag: set[str], tag0group: set[str]) -> bool:
        """
        设置文件tag与tag0group，注意：须满足其if，否则将失败
        :param uid: 文件UID
        :param tag: 文件tag，注意：重复项会被自动去重
        :param tag0group: 文件tag0group，注意：重复项会被自动去重
        :return: 是否设置成功
        """
        cur = self.conn.cursor()
        self.exists_error(cur, tag, tag0group, {uid})

        old_tag, old_tag0group = (to_r_tag(i) for i in cur.execute("SELECT TAG, TAG0GROUP FROM FILE WHERE UID == ?;", (uid,)).fetchall()[0])
        if not old_tag.isdisjoint(tag):
            raise SQLDuplicateValuesError(old_tag.intersection(tag).pop(), "TAG")
        elif not old_tag0group.isdisjoint(tag0group):
            raise SQLDuplicateValuesError(old_tag0group.intersection(tag0group).pop(), "TAG0GROUP")

        text = "UPDATE FILE SET TAG = ?, TAG0GROUP = ? WHERE UID == ?;"
        tag.update(old_tag)
        tag0group.update(old_tag0group)
        if not self.ok_tag0group_in_file(cur, tag, tag0group):
            raise SQLFileIfError()
        tag = self.__to_w_tag(tag)
        tag0group = self.__to_w_tag(tag0group)
        cur.execute(text, (tag, tag0group, uid))
        cur.close()
        return True
    @to_simple_zh(par_str=["new_name"])
    def set_file_name(self, uid: int, new_name: str) -> bool:
        """
        设置文件名称
        :param uid: 文件UID
        :param new_name: 文件新名称
        :return: 是否设置成功
        """
        cur = self.conn.cursor()
        if not self.exist("FILE", uid, cur):
            raise SQLNULLError(uid, "FILE")
        text = "UPDATE FILE SET NAME = ? WHERE UID == ?;"
        cur.execute(text, (new_name, uid))
        cur.close()
        return True
    @to_simple_zh(par_set=["tag", "tag0group"])
    def del_file(self, uid: int, tag: set[str], tag0group: set[str]) -> bool:
        """
        删除文件tag与tag0group，注意：须满足其if，否则将失败
        :param uid: 文件UID
        :param tag: 文件tag，注意：重复项会被自动去重
        :param tag0group: 文件tag0group，注意：重复项会被自动去重
        :return: 是否删除成功
        """
        cur = self.conn.cursor()
        self.exists_error(cur, tag, tag0group, {uid})

        _data = [to_r_tag(i) for i in cur.execute("SELECT TAG, TAG0GROUP FROM FILE WHERE UID == ? LIMIT 1;", (uid,)).fetchall()[0]]
        if not tag.issubset(_data[0]):
            raise SQLValueTagError(tag.symmetric_difference(_data[0]).pop(), "TAG")
        elif not tag0group.issubset(_data[1]):
            raise SQLValueTagError(tag0group.symmetric_difference(_data[1]).pop(), "TAG0GROUP")

        for _d, _i in ((tag, 0), (tag0group, 1)):
            _data[_i].symmetric_difference_update(_d)
        if not self.ok_tag0group_in_file(cur, _data[0], _data[1]):
            raise SQLFileIfError()

        text = "UPDATE FILE SET TAG = ?, TAG0GROUP = ? WHERE UID = ?;"
        cur.execute(text, (self.__to_w_tag(_data[0]), self.__to_w_tag(_data[1]), uid))
        cur.close()
        return True
    def del_file_row(self, uid: int) -> bool:
        """
        删除文件列
        :param uid: 文件UID
        :return: 是否删除成功
        """
        cur = self.conn.cursor()
        if not self.exist("FILE", uid, cur):
            raise SQLNULLError(uid, "FILE")
        text = "DELETE FROM FILE WHERE UID == ?;"
        cur.execute(text, (uid,))
        cur.close()
        return True
    @to_simple_zh(par_str=["key"], par_set=["tag", "tag0group"])
    def select_files(self, key: str|int, _type: int, tag: set[str], tag0group: set[str], count_max: int=1000) -> list[int]:
        """
        根据key、type、tag、tag0group查询文件UID
        特别的，如果存在其tag或tag0group的父级tag0group，直接父级子代tag, 子代tag，被视为满足
        :param key: 查询key，可根据名称或UID查询
        :param _type: 文件类型，参考常量
        :param tag: 文件tag，注意：重复项会被自动去重
        :param tag0group: 文件tag0group，注意：重复项会被自动去重
        :param count_max: 返回的最大数量，默认1000
        :return: 文件UID列表
        """
        cur = self.conn.cursor()
        self.exists_error(cur, tag=tag, tag0group=tag0group)
        # 将tag进行整理，进行同义词组管理
        special_tag, tag = self.__tag_fathers_and_union("TAG", tag)
        special_tag0group, tag0group = self.__tag_fathers_and_union("TAG0GROUP", tag0group)
        # 整理没有父系的tag
        text = " ".join((f"AND INSTR(TAG, \"#{i}#\") > 0" for i in tag))
        text += " ".join((f"AND INSTR(TAG0GROUP, \"#{i}#\") > 0" for i in tag0group))
        # 尝试获取可能的file，无file则省略后续运算
        if isinstance(key, str):
            files = cur.execute(f"SELECT UID, TAG, TAG0GROUP FROM FILE WHERE NAME GLOB(\"*{key}*\") AND TYPE == ? "+text+";",
                                (_type, )).fetchall()
        else:
            files = cur.execute(f"SELECT UID, TAG, TAG0GROUP FROM FILE WHERE UID == ? AND TYPE == ? "+text+";",
                                (key, _type)).fetchall()
        if not files:
            return []
        # 查看是否满足含父系的tag
        true_files = []
        for _uid, _tag, _tag0group in files:
            _tag = to_r_tag(_tag)
            _tag0group = to_r_tag(_tag0group)
            for _t in special_tag:
                if not ((_t[1] & _tag) or (_t[0] & _tag0group)):
                    break
            for _tg in special_tag0group:
                if not (_tg[0] & _tag0group or (_tg[1] & _tag)):
                    break
            true_files.append(_uid)

        cur.close()
        return true_files[:count_max]

    def write_note(self, _type: str, _key: int|str, notes: str) -> bool:
        """
        写入注释
        :param _type: 列类型
        :param _key: 注释key，可根据名称或UID
        :param notes: 注释内容
        :return: 是否写入成功
        """
        cur = self.conn.cursor()
        if _type in ("TAG", "TAG0GROUP"):
            text = f"UPDATE {_type} SET NOTES = ? WHERE NAME == ?"
        elif _type in ("FILE",):
            text = f"UPDATE {_type} SET NOTES = ? WHERE UID == ?"
        else:
            raise ValueError()
        cur.execute(text, (notes, _key))
        cur.close()
        return True
    @to_simple_zh(par_set=["tag", "tag0group"])
    def sort_tag(self, tag: set[str], tag0group: set[str]) -> tuple[set[str], set[str]]:
        """
        将输入值整理进行tag0group归类运算，将被整理为其最父级
        :param tag: 文件tag，注意：重复项会被自动去重
        :param tag0group: 文件tag0group，注意：重复项会被自动去重
        :return: 整理后的tag、tag0group
        """
        cur = self.conn.cursor()

        self.exists_error(cur, tag, tag0group)

        tag = tag.copy()
        tag0group = tag0group.copy()
        tag_del, tag0group_del = set(), set()

        # 筛选出存在in的row
        _data_n = set()
        for _n in cur.execute(f"SELECT IN0GROUP FROM TAG WHERE NAME IN {self.to_tuple(tag)}"):
            _data_n.update(to_r_tag(_n[0]))
        for _n in cur.execute(f"SELECT IN0GROUP FROM TAG0GROUP WHERE NAME IN {self.to_tuple(tag0group)}"):
            _data_n.update(to_r_tag(_n[0]))
        _data = [(_d[0], to_r_tag(_d[1]), to_r_tag(_d[2]), to_r_tag(_d[3]), to_r_tag(_d[4]))
                 for _d in cur.execute(f"SELECT NAME, TAG0IN, TAG0IF, TAG0GROUP0IN, TAG0GROUP0IF FROM TAG0GROUP WHERE NAME IN {self.to_tuple(_data_n)}")]

        # 遍历可能项查找符合组，如果存在，则重遍历直至无更改
        count = [1]
        while count:
            count = []
            for _i in range(len(_data)):
                _n, _tin, _tif, _tgin, _tgif = _data[_i]
                if _tif.issubset(tag) and _tgif.issubset(tag0group):
                    count.append(_i)

                    tag_del.update(_tin), tag0group_del.update(_tgin)
                    tag0group.add(_n)

                    _new_n = to_r_tag(cur.execute("SELECT IN0GROUP FROM TAG0GROUP WHERE NAME == ?;", (_n,)).fetchall()[0][0])
                    _data += [(_d[0], to_r_tag(_d[1]), to_r_tag(_d[2]), to_r_tag(_d[3]), to_r_tag(_d[4]))
                              for _d in cur.execute(f"SELECT NAME, TAG0IN, TAG0IF, TAG0GROUP0IN, TAG0GROUP0IF FROM TAG0GROUP WHERE NAME IN {self.to_tuple(_new_n)}")]

            for _i in count:
                _data.pop(_i)

        tag = tag.difference(tag_del)
        tag0group = tag0group.difference(tag0group_del)
        cur.close()
        return tag, tag0group
    def sort_size(self) -> list[int]:
        """将file的uid进行整理，使其有序化，返回在检测中不存在的uid(末尾为原预期下一个uid)"""
        count = []
        count_null = 0
        count_max = self.cur.execute("SELECT VALUE FROM DATA WHERE NAME == \"file_num\";").fetchall()[0][0]
        for i in range(count_max):
            if not self.exist("FILE", i, self.cur):
                count.append(i)
                count_null += 1
            elif count_null:
                self.cur.execute("UPDATE FILE SET UID = ? WHERE UID == ?;", (i-count_null, i))
        self.cur.execute("UPDATE DATA SET VALUE = ? WHERE NAME == \"file_num\";", (count_max-count_null,))
        count.append(count_max)
        return count
    @staticmethod
    @to_simple_zh(par_str=["key"])
    def exist(_type: typing.Literal["TAG", "TAG0GROUP", "FILE", "DATA"], key: str|int, cur: sqlite3.Cursor) -> bool:
        """检测该列是否存在"""
        if _type in ("TAG", "TAG0GROUP"):
            text = f"SELECT EXISTS( SELECT 1 FROM {_type} WHERE NAME = \"{key}\");"
        elif _type in ("FILE",):
            text = f"SELECT EXISTS( SELECT 1 FROM {_type} WHERE UID = {key});"
        elif _type in ("DATA",):
            text = f"SELECT EXISTS( SELECT 1 FROM {_type} WHERE NAME = \"{key}\");"
        else:
            raise ValueError()

        flag = cur.execute(text).fetchall()[0][0]
        return bool(flag)
    @to_simple_zh(par_set=["tag", "tag0group"])
    def exists(self, _data: dict[str:], cur: sqlite3.Cursor, tag: set[str]=(), tag0group: set[str]=(), file: set[int]=()) -> bool:
        """
        检测输入值是否存在
        :param _data: 输出不存在的对象
        :param cur: sql指针
        :param tag: 文件tag，注意：重复项会被自动去重
        :param tag0group: 文件tag0group，注意：重复项会被自动去重
        :param file: 文件UID，注意：重复项会被自动去重
        :return: 是否存在
        """
        if tag:
            text = f"SELECT NAME FROM TAG WHERE NAME IN {self.to_tuple(tag)};"
            data1 = {r[0] for r in cur.execute(text).fetchall()}
            _data["tag"] = data1.symmetric_difference(tag)
            flag1 = not bool(_data["tag"])
        else:
            _data["tag"] = set()
            flag1 = True
        if tag0group:
            text = f"SELECT NAME FROM TAG0GROUP WHERE NAME IN {self.to_tuple(tag0group)};"
            data2 = {r[0] for r in cur.execute(text).fetchall()}
            _data["tag0group"] = data2.symmetric_difference(tag0group)
            flag2 = not bool(_data["tag0group"])
        else:
            _data["tag0group"] = set()
            flag2 = True
        if file:
            text = f"SELECT UID FROM FILE WHERE UID IN {self.to_tuple(file, False)};"
            data3 = {r[0] for r in cur.execute(text).fetchall()}
            _data["file"] = data3.symmetric_difference(file)
            flag3 = not bool(_data["file"])
        else:
            _data["file"] = set()
            flag3 = True
        return flag1&flag2&flag3
    def exists_error(self, cur: sqlite3.Cursor, tag: set[str]=(), tag0group: set[str]=(), file: set[int]=()):
        """与exists不同，它在不存在时将抛出异常"""
        _data = dict()
        if not self.exists(_data, cur, tag, tag0group, file):
            for _t in _data["tag"]:
                raise SQLNULLError(_t, "TAG")
            for _tg in _data["tag0group"]:
                raise SQLNULLError(_tg, "TAG0GROUP")
            for _f in _data["file"]:
                return SQLNULLError(_f, "FILE")
    @to_simple_zh(par_set=["tag", "tag0group"])
    def ok_tag0group_in_file(self, cur: sqlite3.Cursor, tag: set[str], tag0group: set[str]) -> bool:
        """查看新组是否满足tag0group的if需要"""
        self.exists_error(cur, tag, tag0group)
        need = [set(), set()]
        [(need[0].update(to_r_tag(_t)), need[1].update(to_r_tag(_tg))) for _t, _tg in cur.execute(f"SELECT TAG0IF, TAG0GROUP0IF FROM TAG0GROUP WHERE NAME IN {self.to_tuple(tag0group)};")]
        return need[0].issubset(tag)&need[1].issubset(tag0group)
    def __ok_tag0group_recursion(self, main_name: str, tag0group: set[str]):
        """检查是否存在递归"""
        if not len(tag0group):
            return
        _tag0group = tag0group.copy()
        text = "SELECT TAG0GROUP0IN, TAG0GROUP0IF FROM TAG0GROUP WHERE NAME == ? LIMIT 1;"
        # 为了抛出异常时返回信息选择了效率较低的算法
        while len(_tag0group):
            _tg = _tag0group.pop()
            _in, _need = (to_r_tag(i) for i in self.cur.execute(text, (_tg,)).fetchall()[0])
            _in = _in.union(_need)
            _tag0group = _tag0group.union(_in)
            if main_name in _in:
                raise SQLRecursionError(main_name, _tg)
    def __tag_fathers_and_union(self, _type: typing.Literal["TAG", "TAG0GROUP"], tag: set[str]) -> tuple[list[list[set[str]]], set[str]]:
        """
        获取所有tag或tag0group的父级tag0group，直接父级子代tag, 子代tag
        :param _type: TAG或TAG0GROUP
        :param tag: 名称列
        :return: ([逐个[{同义tag0group}, {同义tag},...],...], {独立项})
        """
        cur = self.conn.cursor()
        tag = tag.copy()
        data = cur.execute(f"SELECT NAME, IN0GROUP FROM {_type} WHERE NAME IN {self.to_tuple(tag)};").fetchall()
        special = list()  # type: list[list[set[str]]]
        for _name, _in in data:
            _in = to_r_tag(_in)
            if not _in:  # 表示tag是独立的
                continue
            tag.remove(_name)
            _all = [_in.copy(), set()]  # type: list[set[str]] # tag名与tag0group分割储存
            _all[1].add(_name)
            # 子代tag
            if _type == "TAG0GROUP":
                _all[1].update(to_r_tag(
                    cur.execute(f"SELECT TAG0IN FROM TAG0GROUP WHERE NAME == ?;", (_name,)).fetchall()[0][0]))
            # 获取全部父级tag0group
            _count = 1
            while _count:
                _d = cur.execute(f"SELECT IN0GROUP FROM TAG0GROUP WHERE NAME IN {self.to_tuple(_in)};").fetchall()
                _in = set()  # 覆盖前文_in，为使代码更简洁
                for _d_in in _d:
                    _in.update(to_r_tag(_d_in[0]))
                if not _in:
                    break
                elif _count == 1: # 直接父系子代tag
                    for _d_in in _d:
                        for _d_in_tg in to_r_tag(_d_in[0]):
                            _all[1].update(to_r_tag(
                                cur.execute(f"SELECT TAG0IN FROM TAG0GROUP WHERE NAME == ?;", (_d_in_tg,)).fetchall()[0][0]))
                _count += 1
                _all[0] = _all[0].union(_in)
            special.append(_all)
        return special, tag

    def split_all_tag(self, path: str) -> bool:
        """
        克隆一个含有全部tag与tag0group的文件库，不含file
        :param path: 存放目录，不可为此实例所用目录
        :return: 是否成功
        """
        if (not os.path.isdir(path)) or (path == self.url):
            return False
        new = self.__class__(path, is_new=True)
        new_cur = new.conn.cursor()
        self.conn.backup(new.conn)
        new_cur.execute("DELETE FROM FILE;")
        new_cur.execute("UPDATE DATA SET VALUE = 0 WHERE NAME == \"file_num\";")
        new.commit()
        new_cur.close()
        del new
        return True
    def split_file_and_tag(self, path: str, file_ids: set[int]) -> bool:
        """
        克隆一个包含指定id的file与相关tag与tag0group的文件库
        :param path: 存放目录，不可为此实例所用目录
        :param file_ids: 文件id列表
        :return: 是否成功
        """
        if (not os.path.isdir(path)) or (path == self.url) or (not self.exists({}, cur=self.conn.cursor(), file=file_ids)):
            return False
        new = self.__class__(path, is_new=True)
        new_cur = new.conn.cursor()
        cur = self.conn.cursor()
        files = cur.execute(f"SELECT * FROM FILE WHERE UID IN {self.to_tuple(file_ids, False)};").fetchall()

        tags = set()
        tag0groups = set()
        for f in files:
            new_cur.execute(f"INSERT INTO FILE VALUES {f};")
            tags.update(to_r_tag(f[4]))
            tag0groups.update(to_r_tag(f[5]))
        new_cur.execute(f"UPDATE DATA SET VALUE = {len(files)} WHERE NAME == \"file_num\";")
        # 获取tag0grop依赖项
        new_tag0group = {_tg for _tg in tag0groups}
        while new_tag0group:
            _d = cur.execute(f"SELECT TAG0IN, TAG0IF, TAG0GROUP0IN, TAG0GROUP0IF FROM TAG0GROUP WHERE NAME IN {self.to_tuple(new_tag0group)};").fetchall()
            new_tag0group.clear()
            for __d in _d:
                tags.update(to_r_tag(__d[0]))
                tags.update(to_r_tag(__d[1]))
                _tg = to_r_tag(__d[2])
                _tg.update(to_r_tag(__d[3]))
                # 取新tag0group
                new_tag0group.update(_tg - tag0groups)
                tag0groups.update(_tg)
        # 导入tag与tag0group
        _d = cur.execute(f"SELECT * FROM TAG WHERE NAME IN {self.to_tuple(tags)};").fetchall()
        for __d in _d:
            # 调整tag的IN0GROUP
            _in = self.__to_w_tag(to_r_tag(__d[2]).intersection(tag0groups))
            __d = __d[:2] + (_in,) + __d[3:]
            new_cur.execute(f"INSERT INTO TAG VALUES {__d};")
        _d = cur.execute(f"SELECT * FROM TAG0GROUP WHERE NAME IN {self.to_tuple(tag0groups)};").fetchall()
        for __d in _d:
            # 调整tag0group的IN0GROUP
            _in = self.__to_w_tag(to_r_tag(__d[6]).intersection(tag0groups))
            __d = __d[:6] + (_in,) + __d[7:]
            new_cur.execute(f"INSERT INTO TAG0GROUP VALUES {__d};")
        new.commit()
        new_cur.close()
        del new
        return True
    @to_simple_zh(par_set=["tag", "tag0group"])
    def split_file_if_tag(self, path: str, tag: set[str], tag0group: set[str]) -> bool:
        """
        克隆一个包含指定tag与tag0group的file的文件库（含关联项）
        :param path: 存放目录，不可为此实例所用目录
        :param tag: tag列表
        :param tag0group: tag0group列表
        :return: 是否成功
        """
        files = self.select_files(key="", tag=tag, tag0group=tag0group)
        return self.split_file_and_tag(path, set(files))
    @to_simple_zh(par_set=["tag", "tag0group"])
    def split_customize(self, path: str, tag: set[str], tag0group: set[str], file: set[int]) -> bool:
        """
        克隆一个包含指定部分的数文件库
        :param path: 存放目录，不可为此实例所用目录
        :param tag: tag列表
        :param tag0group: tag0group列表，不满足的tag子项将被清除
        :param file: file列表，不满足的tag子项将被清除
        :return: 是否成功
        """
        if (not os.path.isdir(path)) or (path == self.url) or (not self.exists({}, cur=self.conn.cursor(), tag=tag, tag0group=tag0group, file=file)):
            return False
        new = self.__class__(path, is_new=True)
        new_cur = new.conn.cursor()
        cur = self.conn.cursor()
        # 导入file
        _d = cur.execute(f"SELECT * FROM FILE WHERE UID IN {self.to_tuple(file, False)};").fetchall()
        for __d in _d:
            # 调整file的TAG与TAG0GROUP
            _tag = self.__to_w_tag(to_r_tag(__d[4]).intersection(tag))
            _tag0group = self.__to_w_tag(to_r_tag(__d[5]).intersection(tag0group))
            __d = __d[:4] + (_tag,) + __d[5:]
            __d = __d[:5] + (_tag0group,) + __d[6:]
            new_cur.execute(f"INSERT INTO FILE VALUES {__d};")
        new_cur.execute(f"UPDATE DATA SET VALUE = {len(_d)} WHERE NAME == \"file_num\";")
        # tag and tag0group
        _d = cur.execute(f"SELECT * FROM TAG WHERE NAME IN {self.to_tuple(tag)};").fetchall()
        for __d in _d:
            # 调整tag的IN0GROUP
            _in = self.__to_w_tag(to_r_tag(__d[2]).intersection(tag0group))
            __d = __d[:2] + (_in,) + __d[3:]
            new_cur.execute(f"INSERT INTO TAG VALUES {__d};")
        _d = cur.execute(f"SELECT * FROM TAG0GROUP WHERE NAME IN {self.to_tuple(tag0group)};").fetchall()
        for __d in _d:
            # 调整tag0group的IN0GROUP, IN, IF
            __t_in = self.__to_w_tag(to_r_tag(__d[2]).intersection(tag))
            __t_if = self.__to_w_tag(to_r_tag(__d[3]).intersection(tag))
            __tg_in = self.__to_w_tag(to_r_tag(__d[4]).intersection(tag0group))
            __tg_if = self.__to_w_tag(to_r_tag(__d[5]).intersection(tag0group))
            __in = self.__to_w_tag(to_r_tag(__d[6]).intersection(tag0group))
            __d = __d[:2] + (__t_in, __t_if, __tg_in, __tg_if, __in) + __d[7:]
            new_cur.execute(f"INSERT INTO TAG0GROUP VALUES {__d};")
        new.commit()
        new_cur.close()
        del new
        return True
    def merge_file(self, other: typing.Self) -> list[tuple[int, int]]:
        """
        合并一个文件库到当前实例，如果其tag不存在则不保留，自动确认更新
        :param other: 另一个文件库实例
        :return: 新项的uid与旧项的uid
        """
        cur = self.conn.cursor()
        other_cur = other.conn.cursor()
        other_files = other_cur.execute("SELECT * FROM FILE;").fetchall()
        nums = []
        for _f in other_files:
            _new = set()
            for _t in to_r_tag(_f[4]):
                if self.exist(_type="TAG", key=_t, cur=cur):
                    _new.add(_t)
            _f = _f[:4] + (self.__to_w_tag(_new),) + _f[5:]
            _new = set()
            for _tg in to_r_tag(_f[5]):
                if self.exist(_type="TAG0GROUP", key=_tg, cur=cur):
                    _new.add(_tg)
            _f = _f[:5] + (self.__to_w_tag(_new),) + _f[6:]
            num = self.new_file(_f[1], _f[2], _f[3], _f[6])
            self.add_file(num, to_r_tag(_f[4]), to_r_tag(_f[5]))
            nums.append((num, _f[0]))
            self.commit()
        return nums
    def merge_all(self, other: typing.Self, is_main: bool=True) -> list[tuple[int, int]]:
        """
        合并一个文件库到当前实例
        :param other: 另一个文件库实例
        :param is_main: 发生冲突时，是否以此库为主
        :return: 新项的uid
        """
        other_cur = other.conn.cursor()
        cur = self.conn.cursor()
        tags = other_cur.execute("SELECT * FROM TAG;").fetchall()
        tag0groups = other_cur.execute("SELECT * FROM TAG0GROUP;").fetchall()
        # 为回避先后顺序冲突，部分直接使用SQL语句，如处理IN0GROUP
        for _t in tags:
            _in = to_r_tag(_t[2])
            if self.exist(_type="TAG", key=_t[0], cur=cur):
                _in = cur.execute(f"SELECT IN0GROUP FROM TAG WHERE NAME == ?;", (_t[0],)).fetchall()[0][0]
                _in = to_r_tag(_in).union(to_r_tag(_t[2]))
                if is_main:
                    self.write_note("TAG", _t[0], _t[3])
            else:
                self.new_tag(_t[0], _t[1], _t[3])
            _in = self.__to_w_tag(_in)
            cur.execute(f"UPDATE TAG SET IN0GROUP = ? WHERE NAME == ?;", (_in, _t[0]))
        for _tg in tag0groups:
            _in = to_r_tag(_tg[6])
            _t_in = to_r_tag(_tg[2])
            _t_if = to_r_tag(_tg[3])
            _tg_in = to_r_tag(_tg[4])
            _tg_if = to_r_tag(_tg[5])
            if self.exist(_type="TAG0GROUP", key=_tg[0], cur=cur):
                _d = cur.execute(
                    f"SELECT TAG0IN, TAG0IF, TAG0GROUP0IN, TAG0GROUP0IF, IN0GROUP FROM TAG0GROUP WHERE NAME == ?;",
                    (_tg[0], )).fetchall()[0]
                _in.update(to_r_tag(_d[4]))
                _t_in.update(to_r_tag(_d[0]))
                _t_if.update(to_r_tag(_d[1]))
                _tg_in.update(to_r_tag(_d[2]))
                _tg_if.update(to_r_tag(_d[3]))
                if is_main:
                    self.write_note("TAG0GROUP", _tg[0], _tg[7])
            else:
                self.new_tag0group(name=_tg[0], _type=_tg[1], notes=_tg[7])
            cur.execute(f"UPDATE TAG0GROUP SET TAG0IN = ?, TAG0IF = ?, TAG0GROUP0IN = ?, TAG0GROUP0IF = ?, IN0GROUP = ? WHERE NAME == ?;",
                        (self.__to_w_tag(_t_in), self.__to_w_tag(_t_if), self.__to_w_tag(_tg_in), self.__to_w_tag(_tg_if), self.__to_w_tag(_in), _tg[0]))
        self.commit()
        nums = self.merge_file(other)
        return nums

    def commit(self):
        self.conn.commit()
    def __del__(self):
        self.conn.commit()
        self.cur.close()
        self.conn.close()

    @staticmethod
    def to_tuple(l: set, is_str: bool=True):
        """整理为供sql语句使用的字符串"""
        if not l:
            return "()"
        if is_str:
            text = "("
            for i in l:
                text += f"\"{i}\","
            text = text[:-1]+")"
        else:
            text = "(" + ",".join(str(i) for i in l) + ")"
        return text
    @staticmethod
    def __to_w_tag(l: set[str]) -> str:
        """将文本以其机械码排序，以'#'间隔，且以'#'开头结尾"""
        l = list(l)
        l.sort()
        return "#" + "#".join(l) + "#" if l else "#"

class Explorer(SQL):
    """在SQL基础上添加了文件处理，对于SQL方法请参考SQL的注释"""
    def __init__(self, url: str, is_new: bool=False):
        """
        初始化Explorer
        :param url: 文件夹地址
        :param is_new: 是否新建数据库
        """
        self.url = url
        self.url_file = join(self.url, URL_FILE_DIR)
        self.url_scratch = join(self.url_file, URL_FILE_SCRATCH_DIR)
        super().__init__(join(self.url, URL_SQL), is_new)
    def create(self) -> bool:
        """
        新建文件库
        :return: 是否成功
        """
        if super().create():
            os.mkdir(self.url_file)
            os.mkdir(join(self.url_file, URL_FILE_SCRATCH_DIR))
            return True
        else:
            return False

    def new_file(self, name: str, _type: int, source: str= "local", notes: str= "无描述") -> int:
        """
        添加文件
        :param name: 文件名
        :param _type: 文件类型
        :param source: 文件来源
        :param notes: 文件描述
        :return: 是否成功
        """
        uid = super().new_file(name, _type, source, notes)
        size = self.cur.execute("SELECT VALUE FROM DATA WHERE NAME == \"file_num\";").fetchall()[0][0]-1
        if not os.path.isdir(join(self.url_file, str(size))):
            os.mkdir(join(self.url_file, str(size)))
        return uid
    def set_file_path(self, uid: int, path: str, is_shear: bool=False) -> bool:
        """
        将path所在文件复制至所在file目录下
        :param uid: 文件UID
        :param path: 文件路径
        :param is_shear: 是否删除源文件
        :return: 是否成功
        """
        if not self.exist("FILE", uid, self.cur):
            raise SQLNULLError(uid, "FILE")
        shutil.copytree(src=path, dst=join(self.url_file, str(uid)), dirs_exist_ok=True)
        if is_shear:
            shutil.rmtree(path=path)
        return True
    def del_file_row(self, uid: int) -> bool:
        """
        删除文件列
        :param uid: 文件UID
        :return: 是否成功
        """
        if super().del_file_row(uid):
            shutil.rmtree(path=join(self.url_file, str(uid)))
            return True
        else:
            return False
    def sort_size(self) -> list[int]:
        sizes = super().sort_size()
        if len(sizes) > 1:
            size = sizes.pop(-1)
            _range = []
            for i in range(len(sizes)-1):
                _range.append((sizes[i]+1, sizes[i+1]))
            _range.append((sizes[-1]+1, size))
            for i in range(len(_range)):
                for _i in range(*_range[i]):
                    os.rename(join(self.url_file, str(_i)), join(self.url_file, str(_i-i-1)))
        return sizes

    def split_file_and_tag(self, path: str, file_ids: set[int]) -> bool:
        """
        克隆一个包含指定id的file与相关tag与tag0group的文件库
        :param path: 存放目录，不可为此实例所用目录
        :param file_ids: 文件id列表
        :return: 是否成功
        """
        if not super().split_file_and_tag(path, file_ids):
            return False
        for _src in file_ids:
            shutil.copytree(join(self.url_file, str(_src)), join(path, URL_FILE_DIR, str(_src)), dirs_exist_ok=True)
        return True
    def split_customize(self, path: str, tag: set[str], tag0group: set[str], file: set[int]) -> bool:
        """
        克隆一个包含指定部分的数文件库
        :param path: 存放目录，不可为此实例所用目录
        :param tag: tag列表
        :param tag0group: tag0group列表，不满足的tag子项将被清除
        :param file: file列表，不满足的tag子项将被清除
        :return: 是否成功
        """
        if not super().split_customize(path, tag, tag0group, file):
            return False
        for _src in file:
            shutil.copytree(join(self.url_file, str(_src)), join(path, URL_FILE_DIR, str(_src)), dirs_exist_ok=True)
        return True
    def merge_file(self, other: typing.Self) -> list[tuple[int, int]]:
        """
        合并一个文件库到当前实例，如果其tag不存在则不保留，自动确认更新
        :param other: 另一个文件库实例
        :return: 新项的uid与旧项的uid
        """
        nums = super().merge_file(other)
        for _dst, _src in nums:
            self.set_file_path(_dst, join(other.url_file, str(_src)))
        return nums

def is_explorer(path: str) -> bool:
    """判断一个地址是否是合法的explorer"""
    paths = os.listdir(path)
    if ("data.db" in paths) and ("save" in paths):

        return True
    else:
        return False
def to_r_tag(l: str) -> set[str]:
    """将IN0GROUP,TAG0IN等标签组分解为包含实际子标签名的set"""
    if len(l) == 1:
        return set()
    else:
        return set(l.split("#")[1:-1])

NAME_FILE_TYPE = ("图集/漫画", "文本/小说", "游戏", "视频")
def get_type_file_id(name: str) -> int:
    """根据名判断类型"""
    for i in range(len(NAME_FILE_TYPE)):
        if name == NAME_FILE_TYPE[i]:
            return i
    return -1

TYPE_FILE_IMAGE = 0
def get_image_cover(path: str|typing.LiteralString) -> tuple[bool, str]:
    """接收一个文件夹地址，查询其是否能找到封面(不包含文件类型检测)，返回bool和封面地址"""
    if not isdir(path):
        return False, r""
    for _path in os.listdir(path):
        if _path[:5] == "00000":
            if isdir(join(path, _path)):
                for __path in os.listdir(join(path, _path)):
                    if __path[:5] == "00000":
                        return True, join(path, _path, __path)
                break
            else:
                return True, join(path, _path)
    return False, r""
def get_image_size(path: str|typing.LiteralString) -> tuple[int, int]:
    """接收一个文件夹地址，查询其总图片数和总文件夹数"""
    if not isdir(path):
        return 0, 0
    size_file = 0
    size_dir = 0
    # 统计
    count_main_file = 0
    for _path in os.listdir(path):
        if _path[:5] == "%05d" % count_main_file and isfile(join(path, _path)):
            size_file += 1
            count_main_file += 1
        elif _path[:6] == "%05d_" % size_dir and isdir(join(path, _path)):
            size_dir += 1
            count = 0
            for __path in os.listdir(join(path, _path)):
                if __path[:5] == "%05d" % count and isfile(join(path, _path, __path)):
                    size_file += 1
                    count += 1
    if not size_dir:
        size_dir = 1
    return size_file, size_dir
TYPE_FILE_TEXT = 1
def get_text_cover(path: str|typing.LiteralString) -> tuple[bool, str]:
    """接收一个文件夹地址，查询其是否能找到封面(不包含文件类型检测)，返回bool和封面地址"""
    if not isdir(path):
        return False, r""
    for _path in os.listdir(path):
        if _path[:6] == "cover.":
            return True, join(path, _path)
    return False, r""
TYPE_FILE_GAME = 2
def get_game_cover(path: str|typing.LiteralString) -> tuple[bool, str]:
    """接收一个文件夹地址，查询其是否能找到封面(不包含文件类型检测)，返回bool和封面地址"""
    if not isdir(path):
        return False, r""
    for _path in os.listdir(path):
        if _path[:6] == "cover.":
            return True, join(path, _path)
TYPE_FILE_VIDEO = 3
def get_video_cover(path: str|typing.LiteralString) -> tuple[bool, str]:
    """接收一个文件夹地址，查询其是否能找到封面(不包含文件类型检测)，返回bool和封面地址"""
    if not isdir(path):
        return False, r""
    for _path in os.listdir(path):
        if _path[:6] == "cover.":
            return True, join(path, _path)
if __name__ == "__main__":
    pass
