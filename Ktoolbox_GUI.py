# -*- coding: utf-8 -*-
#
# BSD 3-Clause License
#
# Copyright (c) 2026, hbyang233 
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met: 
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer. 
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution. [cite: 10]
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission. [cite: 11]
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. [cite: 12]
  
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import subprocess
import os
import ctypes
import json
import re
import sys

# 修复 Windows 高分屏模糊
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

class KToolBoxUltimateGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("KToolBox_GUI")
        self.root.option_add("*Font", ("Microsoft YaHei UI", 10))

        # 1. 读取基础 .env 和 GUI 历史记忆
        self.env_config = self.parse_env_file(".env")
        self.history_config = self.load_gui_history()
        
        self.tk_vars = {}
        self.cli_vars = {}
        self.current_process = None

        # 核心框架布局
        self.main_frame = ttk.Frame(self.root, padding=15)
        self.main_frame.pack(fill="both", expand=True)

        self._build_basic_section()
        self._build_options_bar()  # 替换原来的高级 toggle，加入主题选择
        self._build_advanced_section()
        self._build_log_section()
        self._build_progress_section()

        # 默认隐藏高级设置
        if not self.history_config.get("custom_vars", {}).get("show_adv", False):
            self.advanced_frame.grid_remove()

        # 2. 窗口大小与位置初始化
        saved_geometry = self.history_config.get("geometry", "")
        if saved_geometry:
            self.root.geometry(saved_geometry)
        else:
            # 首次运行：给定一个足够展示所有内容的保底大小
            self.root.geometry("950x850")
            self.root.eval('tk::PlaceWindow . center') # 首次运行居中显示

        # 3. 初始化主题并绑定事件
        self.apply_theme()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ================= 配置读写引擎 =================
    def parse_env_file(self, filepath):
        config = {}
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        config[key.strip()] = val.strip().strip('"').strip("'")
        return config

    def load_gui_history(self):
        if os.path.exists("ktoolbox_gui_history.json"):
            try:
                with open("ktoolbox_gui_history.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _on_closing(self):
        config_to_save = {
            "geometry": self.root.geometry(),  # 记录关闭时的窗口大小和屏幕位置
            "theme": self.theme_var.get(),     # 记录主题
            "url": self.url_entry.get(),
            "cmd": self.cmd_var.get(),
            "save_path": self.save_path_var.get(),
            "tk_vars": {k: v.get() for k, v in self.tk_vars.items()},
            "cli_vars": {k: v.get() for k, v in self.cli_vars.items()},
            "custom_vars": {
                "no_attachments": self.no_attachments_var.get(),
                "dump_json": self.dump_json_var.get(),
                "show_adv": self.show_adv_var.get()
            }
        }
        try:
            with open("ktoolbox_gui_history.json", "w", encoding="utf-8") as f:
                json.dump(config_to_save, f, ensure_ascii=False, indent=4)
        except Exception:
            pass
        
        if self.current_process and self.current_process.poll() is None:
            self.current_process.terminate()
            
        self.root.destroy()

    def _get_default(self, var_type, key, env_fallback):
        if var_type == "tk" and key in self.history_config.get("tk_vars", {}):
            return self.history_config["tk_vars"][key]
        if var_type == "cli" and key in self.history_config.get("cli_vars", {}):
            return self.history_config["cli_vars"][key]
        return self.env_config.get(key, env_fallback)

    # ================= UI 组件工厂 =================
    def _add_entry(self, parent, label, env_key, fallback, row, col, width=20, tip="", colspan=1):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", pady=5, padx=5)
        var = tk.StringVar(value=self._get_default("tk", env_key, fallback))
        self.tk_vars[env_key] = var
        entry = ttk.Entry(parent, textvariable=var, width=width)
        entry.grid(row=row, column=col+1, columnspan=colspan, sticky="w", padx=5)
        if tip:
            ttk.Label(parent, text=tip, foreground="gray", font=("", 8)).grid(row=row, column=col+1+colspan, sticky="w")

    def _add_check(self, parent, label, env_key, fallback_bool, row, col, colspan=2):
        hist_val = self.history_config.get("tk_vars", {}).get(env_key)
        raw_val = hist_val if hist_val is not None else (self.env_config.get(env_key, str(fallback_bool)).lower() == "true")
        var = tk.BooleanVar(value=raw_val)
        self.tk_vars[env_key] = var
        ttk.Checkbutton(parent, text=label, variable=var).grid(row=row, column=col, columnspan=colspan, sticky="w", pady=2, padx=5)

    def _add_list_entry(self, parent, label, env_key, fallback, row, col, width=30):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", pady=5, padx=5)
        hist_val = self.history_config.get("tk_vars", {}).get(env_key)
        if hist_val is not None:
            show_val = hist_val
        else:
            raw_list_str = self.env_config.get(env_key, "[]")
            try:
                show_val = ", ".join(json.loads(raw_list_str))
            except:
                show_val = fallback
        var = tk.StringVar(value=show_val)
        self.tk_vars[env_key] = var
        ttk.Entry(parent, textvariable=var, width=width).grid(row=row, column=col+1, columnspan=2, sticky="we", padx=5)

    # ================= 1. 基础页面 =================
    def _build_basic_section(self):
        basic_lf = ttk.LabelFrame(self.main_frame, text=" 📍 基础下载设置 ", padding=10)
        basic_lf.pack(fill="x", pady=5)

        ttk.Label(basic_lf, text="目标链接:").grid(row=0, column=0, sticky="w", pady=5)
        self.url_entry = ttk.Entry(basic_lf, width=65)
        self.url_entry.insert(0, self.history_config.get("url", ""))
        self.url_entry.grid(row=0, column=1, columnspan=3, sticky="we", padx=5)

        ttk.Label(basic_lf, text="下载模式:").grid(row=1, column=0, sticky="w", pady=5)
        self.cmd_var = tk.StringVar(value=self.history_config.get("cmd", "sync-creator"))
        cmd_menu = ttk.Combobox(basic_lf, textvariable=self.cmd_var, state="readonly", width=15)
        cmd_menu['values'] = ("sync-creator", "download-post", "get-creators")
        cmd_menu.grid(row=1, column=1, sticky="w", padx=5)
        
        ttk.Label(basic_lf, text="保存位置:").grid(row=2, column=0, sticky="w", pady=5)
        self.save_path_var = tk.StringVar(value=self.history_config.get("save_path", os.getcwd()))
        path_frame = ttk.Frame(basic_lf)
        path_frame.grid(row=2, column=1, columnspan=3, sticky="we", padx=5)
        ttk.Entry(path_frame, textvariable=self.save_path_var, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(path_frame, text="浏览...", width=8, command=lambda: self.save_path_var.set(filedialog.askdirectory() or self.save_path_var.get())).pack(side="right", padx=5)

        self._add_entry(basic_lf, "目录命名规则:", "KTOOLBOX_JOB__POST_DIRNAME_FORMAT", "{published}_{title}", 3, 0, width=40)
        
        name_frame = ttk.Frame(basic_lf)
        name_frame.grid(row=4, column=1, columnspan=3, sticky="w", padx=5)
        ttk.Label(name_frame, text="快捷插入: ").pack(side="left")
        for tag in ["{id}", "{title}", "{published}", "{user}"]:
            ttk.Button(name_frame, text=tag, width=8, command=lambda t=tag: self.tk_vars["KTOOLBOX_JOB__POST_DIRNAME_FORMAT"].set(self.tk_vars["KTOOLBOX_JOB__POST_DIRNAME_FORMAT"].get() + t)).pack(side="left", padx=2)

        btn_frame = ttk.Frame(basic_lf)
        btn_frame.grid(row=5, column=0, columnspan=4, sticky="e", pady=(15, 0))
        ttk.Label(btn_frame, text="中断后再次点击启动即可无缝继续下载", foreground="gray", font=("", 8)).pack(side="left", padx=10)
        self.btn_stop = ttk.Button(btn_frame, text="⏹️ 取消下载", command=self.stop_download, state="disabled")
        self.btn_stop.pack(side="left", padx=5)
        self.btn_run = ttk.Button(btn_frame, text="▶️ 启动下载", command=self.start_thread, style="Accent.TButton")
        self.btn_run.pack(side="left", padx=5)

    def _build_options_bar(self):
        """包含高级设置开关、生成配置按钮和主题下拉框的选项栏"""
        opt_frame = ttk.Frame(self.main_frame)
        opt_frame.pack(fill="x", pady=5)
        
        # 1. 高级设置开关
        self.show_adv_var = tk.BooleanVar(value=self.history_config.get("custom_vars", {}).get("show_adv", False))
        ttk.Checkbutton(opt_frame, text="🛠️ 显示高级设置", variable=self.show_adv_var, 
                        command=lambda: self.advanced_frame.pack(fill="x", pady=5, after=self.main_frame.winfo_children()[1]) if self.show_adv_var.get() else self.advanced_frame.pack_forget()).pack(side="left")
        
        # 2. 【新增】生成示例 .env 按钮 
        ttk.Button(opt_frame, text="📄 生成示例配置", command=self.generate_example_env).pack(side="left", padx=10)

        # 3. 主题选择框
        theme_frame = ttk.Frame(opt_frame)
        theme_frame.pack(side="right")
        ttk.Label(theme_frame, text="🎨 主题:").pack(side="left", padx=5)
        self.theme_var = tk.StringVar(value=self.history_config.get("theme", "跟随系统"))
        theme_cb = ttk.Combobox(theme_frame, textvariable=self.theme_var, state="readonly", width=10)
        theme_cb['values'] = ("跟随系统", "浅色", "深色")
        theme_cb.pack(side="left")
        theme_cb.bind("<<ComboboxSelected>>", lambda e: self.apply_theme())

    def generate_example_env(self):
        """生成全量官方参数配置文件并预设优化值"""
        target_dir = self.save_path_var.get()
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        path = os.path.join(target_dir, ".env")
        
        # 使用你提供的全量参数，并填入你的优化预设值
        env_content = f"""# KToolBox 全量配置文件示例
# 预设值已根据你的需求进行优化

# --- API 配置 ---
KTOOLBOX_API__SCHEME=https
KTOOLBOX_API__NETLOC=kemono.cr
KTOOLBOX_API__STATICS_NETLOC=img.kemono.cr
KTOOLBOX_API__FILES_NETLOC=kemono.cr
KTOOLBOX_API__PATH=/api/v1
KTOOLBOX_API__TIMEOUT=5.0
KTOOLBOX_API__RETRY_TIMES=3
KTOOLBOX_API__RETRY_INTERVAL=15.0
KTOOLBOX_API__SESSION_KEY=

# --- 下载器配置 ---
KTOOLBOX_DOWNLOADER__SCHEME=https
KTOOLBOX_DOWNLOADER__TIMEOUT=60.0
KTOOLBOX_DOWNLOADER__ENCODING=utf-8
KTOOLBOX_DOWNLOADER__BUFFER_SIZE=20480
KTOOLBOX_DOWNLOADER__CHUNK_SIZE=1024
KTOOLBOX_DOWNLOADER__TEMP_SUFFIX=tmp
KTOOLBOX_DOWNLOADER__RETRY_TIMES=15
KTOOLBOX_DOWNLOADER__RETRY_STOP_NEVER=False
KTOOLBOX_DOWNLOADER__RETRY_INTERVAL=3.0
KTOOLBOX_DOWNLOADER__TPS_LIMIT=1.0
KTOOLBOX_DOWNLOADER__USE_BUCKET=False
KTOOLBOX_DOWNLOADER__BUCKET_PATH=.ktoolbox\\bucket_storage
KTOOLBOX_DOWNLOADER__REVERSE_PROXY={{}}
KTOOLBOX_DOWNLOADER__KEEP_METADATA=True

# --- 下载任务配置 ---
KTOOLBOX_JOB__COUNT=10
KTOOLBOX_JOB__INCLUDE_REVISIONS=False
KTOOLBOX_JOB__POST_DIRNAME_FORMAT="{{title}} [{{published}}]"
KTOOLBOX_JOB__POST_STRUCTURE__ATTACHMENTS=.
KTOOLBOX_JOB__POST_STRUCTURE__CONTENT=content.txt
KTOOLBOX_JOB__POST_STRUCTURE__EXTERNAL_LINKS=external_links.txt
KTOOLBOX_JOB__POST_STRUCTURE__FILE={{id}}_{{}}
KTOOLBOX_JOB__POST_STRUCTURE__REVISIONS=revisions
KTOOLBOX_JOB__MIX_POSTS=False
KTOOLBOX_JOB__SEQUENTIAL_FILENAME=False
KTOOLBOX_JOB__SEQUENTIAL_FILENAME_EXCLUDES=["*.zip", "*.mp4", "*.psd"]
KTOOLBOX_JOB__FILENAME_FORMAT={{}}
KTOOLBOX_JOB__ALLOW_LIST=[]
KTOOLBOX_JOB__BLOCK_LIST=[]
KTOOLBOX_JOB__EXTRACT_CONTENT=False
KTOOLBOX_JOB__EXTRACT_CONTENT_IMAGES=False
KTOOLBOX_JOB__EXTRACT_EXTERNAL_LINKS=False
KTOOLBOX_JOB__GROUP_BY_YEAR=False
KTOOLBOX_JOB__GROUP_BY_MONTH=False
KTOOLBOX_JOB__YEAR_DIRNAME_FORMAT={{year}}
KTOOLBOX_JOB__MONTH_DIRNAME_FORMAT={{year}}-{{month:02d}}
KTOOLBOX_JOB__KEYWORDS=[]
KTOOLBOX_JOB__KEYWORDS_EXCLUDE=["WIP", "Sketch", "Preview", "草图", "预览", "poll"]
KTOOLBOX_JOB__DOWNLOAD_FILE=True
KTOOLBOX_JOB__DOWNLOAD_ATTACHMENTS=True
KTOOLBOX_JOB__MIN_FILE_SIZE=
KTOOLBOX_JOB__MAX_FILE_SIZE=

# --- 其他配置 ---
KTOOLBOX_LOGGER__LEVEL=DEBUG
KTOOLBOX_SSL_VERIFY=True
KTOOLBOX_JSON_DUMP_INDENT=4
KTOOLBOX_USE_UVLOOP=False
"""
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(env_content)
            
            self.safe_log(f"[√] 全量配置文件已生成: {path}\n")
            if messagebox.askyesno("生成成功", f"全量配置文件已保存至:\n{path}\n\n是否立即打开编辑？"):
                os.startfile(path)
        except Exception as e:
            messagebox.showerror("错误", f"生成失败: {str(e)}")

    # ================= 原生主题与暗黑模式黑科技 =================
    def _get_system_theme(self):
        """通过读取注册表判断 Windows 10/11 的系统主题"""
        if sys.platform != "win32": return "light"
        try:
            import winreg
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if value == 1 else "dark"
        except Exception:
            return "light"

    def _set_titlebar_color(self, is_dark):
        """调用 Windows DWM API 强制修改窗口标题栏颜色"""
        if sys.platform != "win32": return
        try:
            self.root.update() # 确保窗口已创建
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            DWMWA_USE_IMMERSIVE_DARK_MODE_V2 = 19
            val = ctypes.c_int(1 if is_dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(val), ctypes.sizeof(val))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_V2, ctypes.byref(val), ctypes.sizeof(val))
        except Exception:
            pass

    def apply_theme(self):
        """应用原生 Tkinter 样式的明暗主题"""
        choice = self.theme_var.get()
        mode = self._get_system_theme() if choice == "跟随系统" else ("dark" if choice == "深色" else "light")
        
        style = ttk.Style()
        self._set_titlebar_color(mode == "dark")

        if mode == "dark":
            style.theme_use("clam") # clam 是 Tkinter 原生中最适合做暗黑魔改的主题
            bg_color, fg_color, input_bg = "#2b2b2b", "#dddddd", "#3c3f41"
            self.root.configure(bg=bg_color)
            style.configure(".", background=bg_color, foreground=fg_color, fieldbackground=input_bg, insertcolor=fg_color)
            style.configure("TButton", background="#444444", foreground=fg_color, borderwidth=1)
            style.map("TButton", background=[("active", "#555555")])
            style.configure("TLabelframe", background=bg_color, foreground=fg_color, bordercolor="#555555")
            style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color)
            style.configure("TNotebook", background=bg_color)
            style.configure("TNotebook.Tab", background="#3c3f41", foreground=fg_color)
            style.map("TNotebook.Tab", background=[("selected", "#525252")])
            style.configure("TCheckbutton", background=bg_color, foreground=fg_color)
            style.map("TCheckbutton", background=[("active", bg_color)])
            
            if hasattr(self, 'log_text'):
                self.log_text.config(bg="#1e1e1e", fg="#a6e22e", insertbackground="#ffffff")
        else:
            try: style.theme_use("vista") # 恢复 Windows 默认主题
            except: style.theme_use("default")
            self.root.configure(bg="SystemButtonFace")
            if hasattr(self, 'log_text'):
                self.log_text.config(bg="#1e1e1e", fg="#a6e22e", insertbackground="#ffffff") # 日志框保持护眼黑底绿字

    # ================= 2. 高级设置选项卡 =================
    def _build_advanced_section(self):
        self.advanced_frame = ttk.Notebook(self.main_frame)
        
        tab_struct = ttk.Frame(self.advanced_frame, padding=10)
        self.advanced_frame.add(tab_struct, text=" 文件与结构 ")
        
        c_vars = self.history_config.get("custom_vars", {})
        self.no_attachments_var = tk.BooleanVar(value=c_vars.get("no_attachments", True))
        self.dump_json_var = tk.BooleanVar(value=c_vars.get("dump_json", False))
        
        ttk.Checkbutton(tab_struct, text="直接将文件存在帖子根目录 (不创建 attachments 文件夹)", variable=self.no_attachments_var).grid(row=0, column=0, columnspan=4, sticky="w", pady=2)
        ttk.Checkbutton(tab_struct, text="下载网页本体元数据 (保存 post.json)", variable=self.dump_json_var).grid(row=1, column=0, columnspan=4, sticky="w", pady=2)

        ttk.Separator(tab_struct, orient="horizontal").grid(row=2, column=0, columnspan=4, sticky="we", pady=10)

        self._add_check(tab_struct, "绝对扁平化 (连帖子文件夹都不建，图片全放画师根目录)", "KTOOLBOX_JOB__MIX_POSTS", False, 3, 0, colspan=4)
        self._add_check(tab_struct, "附件按数字顺次重命名 (1.jpg, 2.jpg...)", "KTOOLBOX_JOB__SEQUENTIAL_FILENAME", True, 4, 0, colspan=4)
        
        self._add_entry(tab_struct, "文件命名规则:", "KTOOLBOX_JOB__FILENAME_FORMAT", "{}", 5, 0)
        self._add_list_entry(tab_struct, "不重命名的格式:", "KTOOLBOX_JOB__SEQUENTIAL_FILENAME_EXCLUDES", "*.psd, *.zip", 5, 2)

        ttk.Separator(tab_struct, orient="horizontal").grid(row=6, column=0, columnspan=4, sticky="we", pady=10)
        
        self._add_check(tab_struct, "按年份分组", "KTOOLBOX_JOB__GROUP_BY_YEAR", False, 7, 0)
        self._add_check(tab_struct, "按月份分组", "KTOOLBOX_JOB__GROUP_BY_MONTH", False, 7, 2)

        tab_filter = ttk.Frame(self.advanced_frame, padding=10)
        self.advanced_frame.add(tab_filter, text=" 筛选与提取 ")
        
        # 增加第四个参数作为提示文字 (Tip)
        for i, (key, label, width, tip) in enumerate([
            ("length", "抓取数量 (留空全下):", 10, ""), 
            ("offset", "起始偏移量:", 10, "例:设10则从第11个下"), 
            ("start-time", "开始时间 (YYYY-MM-DD):", 15, ""), 
            ("end-time", "结束时间:", 15, ""),
            ("keywords", "标题包含关键词 (逗号分隔):", 25, ""), 
            ("keywords-exclude", "标题排除关键词:", 25, "")
        ]):
            ttk.Label(tab_filter, text=label).grid(row=i//2, column=(i%2)*2, sticky="w", pady=5)
            var = tk.StringVar(value=self._get_default("cli", key, ""))
            self.cli_vars[key] = var
            # 这里的 pady 和 padx 确保输入框和提示文字有间距
            entry = ttk.Entry(tab_filter, textvariable=var, width=width)
            entry.grid(row=i//2, column=(i%2)*2+1, sticky="w", padx=5)
            if tip:
                ttk.Label(tab_filter, text=tip, foreground="gray", font=("", 8)).grid(row=i//2, column=(i%2)*2+1, sticky="e", padx=(width*7, 0))

        ttk.Separator(tab_filter, orient="horizontal").grid(row=3, column=0, columnspan=4, sticky="we", pady=10)
        self._add_list_entry(tab_filter, "排除特定格式 (Block List):", "KTOOLBOX_JOB__BLOCK_LIST", "*.psd, *.zip", 4, 0, width=25)
        self._add_list_entry(tab_filter, "仅下载特定格式 (Allow List):", "KTOOLBOX_JOB__ALLOW_LIST", "", 4, 2, width=25)

        tab_net = ttk.Frame(self.advanced_frame, padding=10)
        self.advanced_frame.add(tab_net, text=" 🌐 网络与防封 ")

        self._add_entry(tab_net, "并发下载数 (Count):", "KTOOLBOX_JOB__COUNT", "4", 0, 0)
        self._add_entry(tab_net, "请求速率限制 (TPS Limit):", "KTOOLBOX_DOWNLOADER__TPS_LIMIT", "5.0", 0, 2)
        self._add_entry(tab_net, "下载超时时间 (秒):", "KTOOLBOX_DOWNLOADER__TIMEOUT", "30.0", 1, 0)
        self._add_entry(tab_net, "下载失败重试次数:", "KTOOLBOX_DOWNLOADER__RETRY_TIMES", "10", 1, 2)
        self._add_entry(tab_net, "API 封锁等待 (秒):", "KTOOLBOX_API__RETRY_INTERVAL", "2.0", 2, 0)
        self._add_entry(tab_net, "Session Key:", "KTOOLBOX_API__SESSION_KEY", "", 3, 0, width=40, colspan=3)

    # ================= 3. 终端日志与进度条 =================
    def _build_log_section(self):
        self.log_text = tk.Text(self.main_frame, height=10, background="#1e1e1e", foreground="#a6e22e", font=("Consolas", 10), padx=5, pady=5)
        self.log_text.pack(fill="both", expand=True, pady=10)

    def _build_progress_section(self):
        prog_frame = ttk.Frame(self.main_frame)
        prog_frame.pack(fill="x", pady=5)
        
        self.progress_var = tk.DoubleVar(value=0)
        self.prog_bar = ttk.Progressbar(prog_frame, variable=self.progress_var, maximum=100, length=400)
        self.prog_bar.pack(side="left", padx=5)

        self.speed_var = tk.StringVar(value="网速: --")
        ttk.Label(prog_frame, textvariable=self.speed_var, font=("Consolas", 10), width=15).pack(side="left", padx=10)

        self.eta_var = tk.StringVar(value="剩余: --:--")
        ttk.Label(prog_frame, textvariable=self.eta_var, font=("Consolas", 10)).pack(side="left", padx=10)

    # ================= 4. 核心调度与控制 =================
    def get_injected_env(self):
        env = os.environ.copy()
        for key, tk_var in self.tk_vars.items():
            val = tk_var.get()
            if isinstance(tk_var, tk.BooleanVar):
                env[key] = str(val)
            elif key in ["KTOOLBOX_JOB__BLOCK_LIST", "KTOOLBOX_JOB__ALLOW_LIST", "KTOOLBOX_JOB__SEQUENTIAL_FILENAME_EXCLUDES"]:
                list_val = [x.strip() for x in val.split(",") if x.strip()]
                env[key] = json.dumps(list_val) if list_val else "[]"
            else:
                if val: env[key] = str(val)
        
        if self.no_attachments_var.get():
            env["KTOOLBOX_JOB__POST_STRUCTURE__ATTACHMENTS"] = "."
            
        env["KTOOLBOX__USE_UVLOOP"] = "False" 
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        env["FORCE_COLOR"] = "1"
        env["RICH_FORCE_COLOR"] = "1"
        env["TERM"] = "xterm-256color"
        return env

    def build_args(self):
        url = self.url_entry.get().strip()
        cmd = self.cmd_var.get()
        if not url:
            messagebox.showwarning("提示", "请输入目标链接！")
            return None

        args = ["ktoolbox", cmd, "--url", url]

        if cmd == "sync-creator":
            for key, tk_var in self.cli_vars.items():
                val = tk_var.get().strip()
                if val:
                    args.extend([f"--{key}", val])

        return args

    def start_thread(self):
        args = self.build_args()
        if args:
            self.btn_run.config(state="disabled")
            self.btn_stop.config(state="normal")
            self.progress_var.set(0)
            threading.Thread(target=self.run_process, args=(args,), daemon=True).start()

    def stop_download(self):
        if self.current_process and self.current_process.poll() is None:
            self.safe_log("\n[!] 正在发送中断信号，停止当前下载...\n")
            self.current_process.terminate()
            self.btn_stop.config(state="disabled")

    def safe_log(self, text):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def run_process(self, args):
        self.root.after(0, self.safe_log, f"[$] 保存路径: {self.save_path_var.get()}\n[$] 核心指令: {' '.join(args)}\n\n")
        
        try:
            CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
            
            self.current_process = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                env=self.get_injected_env(), cwd=self.save_path_var.get(), 
                encoding="utf-8", errors="replace", bufsize=1, universal_newlines=True,
                creationflags=CREATE_NO_WINDOW
            )
            
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            prog_re = re.compile(r'(\d{1,3})%')
            speed_re = re.compile(r'([\d.]+\s*[kKMmGg][bB]/s)', re.I)
            eta_re = re.compile(r'(?:ETA|<|剩余|00:)?\s*(\d{1,2}:\d{2}(?::\d{2})?)', re.I)

            buffer = ""
            while True:
                char = self.current_process.stdout.read(1)
                if not char and self.current_process.poll() is not None:
                    break
                
                if char:
                    buffer += char
                    if char in ['\r', '\n']:
                        clean_line = ansi_escape.sub('', buffer)
                        
                        p = prog_re.search(clean_line)
                        s = speed_re.search(clean_line)
                        e = eta_re.search(clean_line)
                        
                        if p: self.root.after(0, self.progress_var.set, float(p.group(1)))
                        if s: self.root.after(0, self.speed_var.set, f"网速: {s.group(1)}")
                        if e: self.root.after(0, self.eta_var.set, f"剩余: {e.group(1)}")

                        if char == '\n' and not p: 
                            self.root.after(0, self.safe_log, clean_line)

                        buffer = ""

            if self.current_process.returncode == 0:
                self.root.after(0, self.progress_var.set, 100.0)
                self.root.after(0, self.speed_var.set, "网速: 0 B/s")
                self.root.after(0, self.eta_var.set, "完成")
                
                banner = "\n" + "="*40 + "\n          🎉 下载任务完美收工！\n" + "="*40 + "\n"
                self.root.after(0, self.safe_log, banner)
                self.root.after(0, lambda: messagebox.showinfo("下载完成", "所有的下载任务已顺利完成！\n文件已存入您的目标文件夹。"))
                
                if not self.dump_json_var.get():
                    self.root.after(0, self.safe_log, "[*] 正在为你清理网页本体 JSON 数据 (post.json)...\n")
                    cleaned_count = 0
                    for root_dir, dirs, files in os.walk(self.save_path_var.get()):
                        if "post.json" in files:
                            try:
                                os.remove(os.path.join(root_dir, "post.json"))
                                cleaned_count += 1
                            except Exception:
                                pass
                    if cleaned_count > 0:
                        self.root.after(0, self.safe_log, f"[√] 已成功清理 {cleaned_count} 个多余的 JSON 文件。\n")
            else:
                self.root.after(0, self.safe_log, f"\n[!] 任务被终止或发生异常，退出码: {self.current_process.returncode}\n")

        except Exception as e:
            self.root.after(0, self.safe_log, f"\n[X] 发生致命错误: {str(e)}\n")
        finally:
            self.current_process = None
            self.root.after(0, lambda: self.btn_run.config(state="normal"))
            self.root.after(0, lambda: self.btn_stop.config(state="disabled"))

if __name__ == "__main__":
    root = tk.Tk()
    app = KToolBoxUltimateGUI(root)
    root.mainloop()