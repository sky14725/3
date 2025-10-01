import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, messagebox, filedialog
import subprocess
import threading
import time
import random
import os
import sys
import json
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class RouterRebootApp:
    def __init__(self, root):
        self.root = root
        self.root.title("光猫重启助手")
        self.root.geometry("850x700")
        self.root.resizable(True, True)
        
        # 先初始化日志相关属性为None
        self.log_text = None
        
        # 配置文件目录和默认配置
        self.config_dir = os.path.join(os.path.dirname(__file__), "configs")
        self.default_config_path = os.path.join(self.config_dir, "default.json")
        self.last_used_config_path = os.path.join(self.config_dir, "last_used.json")
        
        # 确保配置目录存在
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        
        # 创建样式 (先于UI创建)
        self.style = ttk.Style()
        self.setup_styles()
        
        # 先初始化UI (确保log_text被创建)
        self.init_ui()
        
        # 再加载配置 (此时log_text已存在)
        self.config = self.load_config_with_prompt()
        
        # 定时任务状态
        self.scheduled_task_running = False
        self.scheduled_task_thread = None
        self.stop_event = threading.Event()
        
        # 刷新WiFi列表和配置列表
        self.refresh_wifi_list()
        self.refresh_config_list()
        
    def setup_styles(self):
        """设置界面样式"""
        self.style.theme_use('clam')
        
        # 主色调：蓝色系
        primary_color = "#4a89dc"
        secondary_color = "#3b73b9"
        light_color = "#ebf2fa"
        text_color = "#2c3e50"
        
        # 标签页样式
        self.style.configure("TNotebook", background=light_color, borderwidth=0)
        self.style.configure("TNotebook.Tab", 
                            background=light_color, 
                            foreground=text_color,
                            padding=[12, 6], 
                            font=("SimHei", 10, "bold"),
                            borderwidth=1)
        self.style.map("TNotebook.Tab", 
                      background=[("selected", "#ffffff")],
                      foreground=[("selected", primary_color)],
                      expand=[("selected", [1, 1, 1, 0])])
        
        # 其他样式配置...
        self.style.configure("TFrame", background="#ffffff")
        self.style.configure("TLabel", 
                            background="#ffffff", 
                            foreground=text_color,
                            font=("SimHei", 10))
        
        self.style.configure("TButton", 
                            font=("SimHei", 10), 
                            padding=6,
                            background=primary_color,
                            foreground="#ffffff",
                            borderwidth=0)
        self.style.map("TButton",
                      background=[("active", secondary_color),
                                 ("pressed", secondary_color)])
        
        self.style.configure("TLabelframe", 
                            background="#ffffff", 
                            font=("SimHei", 10, "bold"),
                            foreground=text_color)
        self.style.configure("TLabelframe.Label", 
                            background="#ffffff",
                            foreground=text_color,
                            padding=[5, 2])
        
        self.style.configure("TProgressbar",
                            thickness=8,
                            troughcolor="#e0e0e0",
                            background=primary_color)
        self.style.map("TProgressbar",
                      background=[("active", secondary_color)])
        
        self.style.configure("TEntry",
                            padding=5,
                            font=("SimHei", 10),
                            fieldbackground="#f9f9f9",
                            borderwidth=1,
                            focusthickness=2,
                            focuscolor=primary_color)

    def init_ui(self):
        # 创建标签页
        tab_control = ttk.Notebook(self.root)
        tab_control.pack(expand=1, fill="both", padx=10, pady=10)
        
        # 主功能标签页
        main_tab = ttk.Frame(tab_control)
        tab_control.add(main_tab, text="主功能")
        
        # 配置标签页 - 合并光猫配置和WiFi设置
        config_tab = ttk.Frame(tab_control)
        tab_control.add(config_tab, text="配置管理")
        
        # 定时任务标签页
        schedule_tab = ttk.Frame(tab_control)
        tab_control.add(schedule_tab, text="定时任务")
        
        # 配置管理标签页 - 新增配置文件管理功能
        config_file_tab = ttk.Frame(tab_control)
        tab_control.add(config_file_tab, text="配置文件")
        
        # 初始化各标签页
        self.setup_main_tab(main_tab)  # 先创建主标签页，确保log_text存在
        self.setup_combined_config_tab(config_tab)
        self.setup_schedule_tab(schedule_tab)
        self.setup_config_file_tab(config_file_tab)
        
    def setup_main_tab(self, parent):
        parent.configure(style="TFrame")
        
        # 进度条区域
        progress_frame = ttk.LabelFrame(parent, text="操作进度", padding=10)
        progress_frame.pack(fill="x", padx=10, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, length=100)
        self.progress_bar.pack(fill="x", padx=5, pady=5)
        
        self.progress_label = ttk.Label(progress_frame, text="准备就绪", anchor="center")
        self.progress_label.pack(fill="x", pady=2)
        
        # 日志区域 - 确保log_text被初始化
        log_frame = ttk.LabelFrame(parent, text="操作日志", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state="disabled", 
                                                font=("SimHei", 10),
                                                bg="#f9f9f9",
                                                relief=tk.FLAT,
                                                bd=1)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 按钮区域
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        self.reboot_btn = ttk.Button(btn_frame, text="重启光猫", command=self.start_reboot_thread)
        self.reboot_btn.pack(side="left", padx=5)
        
        self.connect_wifi_btn = ttk.Button(btn_frame, text="连接WiFi", command=self.start_wifi_thread)
        self.connect_wifi_btn.pack(side="left", padx=5)
        
        self.clear_log_btn = ttk.Button(btn_frame, text="清空日志", command=self.clear_log)
        self.clear_log_btn.pack(side="right", padx=5)
        
        # ASCII艺术
        self.ascii_label = ttk.Label(parent, text="", font=("Consolas", 8), background="#ffffff")
        self.ascii_label.pack(fill="x", padx=10, pady=5)
        self.update_ascii_art()

    # 以下为其他方法，保持不变...
    def setup_combined_config_tab(self, parent):
        """合并光猫配置和WiFi设置的标签页"""
        parent.configure(style="TFrame")
        
        # 创建配置和WiFi的分隔面板
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 光猫配置子面板
        router_frame = ttk.Frame(notebook)
        notebook.add(router_frame, text="光猫设置")
        
        # WiFi配置子面板
        wifi_frame = ttk.Frame(notebook)
        notebook.add(wifi_frame, text="WiFi设置")
        
        # 光猫配置内容
        self.setup_router_config(router_frame)
        
        # WiFi配置内容
        self.setup_wifi_config(wifi_frame)
        
        # 底部保存按钮
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        save_btn = ttk.Button(btn_frame, text="保存配置", command=self.save_config)
        save_btn.pack(side="left", padx=5)
        
        reset_btn = ttk.Button(btn_frame, text="恢复默认", command=self.reset_to_default)
        reset_btn.pack(side="left", padx=5)
    
    def setup_router_config(self, parent):
        """光猫配置内容"""
        config_frame = ttk.LabelFrame(parent, text="光猫参数", padding=10)
        config_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        form_frame = ttk.Frame(config_frame)
        form_frame.pack(padx=20, pady=20, fill="x")
        form_frame.columnconfigure(1, weight=1)
        
        # IP地址
        ttk.Label(form_frame, text="路由器IP:").grid(row=0, column=0, sticky="w", pady=5)
        self.router_ip_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.router_ip_var).grid(row=0, column=1, sticky="ew", pady=5, padx=5)
        
        # 登录地址
        ttk.Label(form_frame, text="登录地址:").grid(row=1, column=0, sticky="w", pady=5)
        self.login_url_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.login_url_var).grid(row=1, column=1, sticky="ew", pady=5, padx=5)
        
        # 起始页地址
        ttk.Label(form_frame, text="起始页地址:").grid(row=2, column=0, sticky="w", pady=5)
        self.start_page_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.start_page_var).grid(row=2, column=1, sticky="ew", pady=5, padx=5)
        
        # 管理地址
        ttk.Label(form_frame, text="管理地址:").grid(row=3, column=0, sticky="w", pady=5)
        self.manage_url_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.manage_url_var).grid(row=3, column=1, sticky="ew", pady=5, padx=5)
        
        # 用户名
        ttk.Label(form_frame, text="用户名:").grid(row=4, column=0, sticky="w", pady=5)
        self.username_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.username_var).grid(row=4, column=1, sticky="ew", pady=5, padx=5)
        
        # 密码
        ttk.Label(form_frame, text="密码:").grid(row=5, column=0, sticky="w", pady=5)
        self.password_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.password_var, show="*").grid(row=5, column=1, sticky="ew", pady=5, padx=5)
    
    def setup_wifi_config(self, parent):
        """WiFi配置内容"""
        wifi_frame = ttk.LabelFrame(parent, text="WiFi列表", padding=10)
        wifi_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        list_frame = ttk.Frame(wifi_frame)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.wifi_listbox = tk.Listbox(list_frame, height=10, font=("SimHei", 10),
                                      bg="#f9f9f9",
                                      bd=1,
                                      relief=tk.FLAT)
        self.wifi_listbox.pack(side="left", fill="both", expand=True)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.wifi_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.wifi_listbox.config(yscrollcommand=scrollbar.set)
        
        # 按钮区域
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        add_btn = ttk.Button(btn_frame, text="添加WiFi", command=self.add_wifi)
        add_btn.pack(side="left", padx=5)
        
        edit_btn = ttk.Button(btn_frame, text="编辑WiFi", command=self.edit_wifi)
        edit_btn.pack(side="left", padx=5)
        
        delete_btn = ttk.Button(btn_frame, text="删除WiFi", command=self.delete_wifi)
        delete_btn.pack(side="left", padx=5)
    
    def setup_schedule_tab(self, parent):
        parent.configure(style="TFrame")
        
        schedule_frame = ttk.LabelFrame(parent, text="定时任务设置", padding=10)
        schedule_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 时间间隔设置
        interval_frame = ttk.Frame(schedule_frame)
        interval_frame.pack(fill="x", padx=20, pady=15)
        
        ttk.Label(interval_frame, text="自动执行间隔:").grid(row=0, column=0, sticky="w", pady=5)
        self.interval_var = tk.IntVar(value=24)
        ttk.Spinbox(interval_frame, from_=1, to=999, textvariable=self.interval_var, width=8).grid(
            row=0, column=1, sticky="w", pady=5, padx=5)
        
        # 时间单位选择下拉框
        self.interval_unit_var = tk.StringVar(value="时")
        unit_combobox = ttk.Combobox(interval_frame, textvariable=self.interval_unit_var, 
                                    values=["秒", "分", "时"], width=5, state="readonly")
        unit_combobox.grid(row=0, column=2, sticky="w", pady=5, padx=5)
        
        # 任务状态和下次执行时间
        status_frame = ttk.Frame(schedule_frame)
        status_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Label(status_frame, text="任务状态:").grid(row=0, column=0, sticky="w", pady=5)
        self.status_var = tk.StringVar(value="未运行")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, foreground="red")
        self.status_label.grid(row=0, column=1, sticky="w", pady=5, padx=5)
        
        next_run_frame = ttk.Frame(schedule_frame)
        next_run_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Label(next_run_frame, text="下次执行时间:").grid(row=0, column=0, sticky="w", pady=5)
        self.next_run_var = tk.StringVar(value="--")
        ttk.Label(next_run_frame, textvariable=self.next_run_var).grid(
            row=0, column=1, sticky="w", pady=5, padx=5)
        
        # 按钮区域
        btn_frame = ttk.Frame(schedule_frame)
        btn_frame.pack(fill="x", padx=20, pady=20)
        
        self.start_schedule_btn = ttk.Button(btn_frame, text="启动定时任务", command=self.start_scheduled_task)
        self.start_schedule_btn.pack(side="left", padx=10)
        
        self.stop_schedule_btn = ttk.Button(btn_frame, text="停止定时任务", command=self.stop_scheduled_task, state="disabled")
        self.stop_schedule_btn.pack(side="left", padx=10)
    
    def setup_config_file_tab(self, parent):
        """配置文件管理标签页"""
        parent.configure(style="TFrame")
        
        config_frame = ttk.LabelFrame(parent, text="配置文件管理", padding=10)
        config_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 配置文件列表
        list_frame = ttk.Frame(config_frame)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ttk.Label(list_frame, text="已保存的配置文件在\_internal\configs目录:").pack(anchor="w", pady=5)
        
        self.config_listbox = tk.Listbox(list_frame, height=8, font=("SimHei", 10),
                                        bg="#f9f9f9",
                                        bd=1,
                                        relief=tk.FLAT)
        self.config_listbox.pack(side="left", fill="both", expand=True)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.config_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.config_listbox.config(yscrollcommand=scrollbar.set)
        
        # 按钮区域
        btn_frame = ttk.Frame(config_frame)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        load_btn = ttk.Button(btn_frame, text="加载选中配置", command=self.load_selected_config)
        load_btn.pack(side="left", padx=5)
        
        save_as_btn = ttk.Button(btn_frame, text="另存为新配置", command=self.save_config_as)
        save_as_btn.pack(side="left", padx=5)
        
        delete_btn = ttk.Button(btn_frame, text="删除选中配置", command=self.delete_selected_config)
        delete_btn.pack(side="left", padx=5)
        
        # 说明文本
        note_frame = ttk.LabelFrame(config_frame, text="说明")
        note_frame.pack(fill="x", padx=10, pady=10)
        
        note_text = """- 默认配置：程序初始设置，不会被修改
- 上次使用：自动保存的上次运行配置
- 可将常用配置另存为不同文件，方便切换使用
"""
        ttk.Label(note_frame, text=note_text, justify="left").pack(padx=10, pady=10, fill="x")
    
    # 配置文件管理相关方法
    def get_default_config(self):
        """获取默认配置"""
        return {
            "router_ip": "192.168.1.1",
            "login_url": "http://{router_ip}/",
            "start_page_url": "http://{router_ip}/",
            "manage_url": "http://{router_ip}/",
            "username": "user",
            "password": "",
            "wifi_list": [],
            "auto_interval": 24,
            "interval_unit": "时"
        }
    
    def save_default_config(self):
        """保存默认配置到文件"""
        with open(self.default_config_path, 'w', encoding='utf-8') as f:
            json.dump(self.get_default_config(), f, ensure_ascii=False, indent=2)
    
    def load_config_with_prompt(self):
        """启动时询问用户是否加载上次配置"""
        # 确保默认配置存在
        if not os.path.exists(self.default_config_path):
            self.save_default_config()
            
        # 检查是否有上次使用的配置
        if os.path.exists(self.last_used_config_path):
            # 询问用户
            answer = messagebox.askyesnocancel(
                "加载配置", 
                "检测到上次使用的配置，是否加载？\n是：加载上次配置\n否：使用默认配置\n取消：手动选择配置"
            )
            
            if answer is True:
                # 加载上次使用的配置
                return self.load_config(self.last_used_config_path)
            elif answer is False:
                # 使用默认配置
                return self.load_config(self.default_config_path)
            else:
                # 手动选择配置
                return self.choose_and_load_config()
        
        # 没有上次配置，使用默认配置
        return self.load_config(self.default_config_path)
    
    def choose_and_load_config(self):
        """让用户手动选择配置文件"""
        config_files = [f for f in os.listdir(self.config_dir) if f.endswith('.json')]
        
        if not config_files:
            messagebox.showinfo("提示", "没有找到配置文件，使用默认配置")
            return self.get_default_config()
            
        # 创建选择对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("选择配置文件")
        dialog.geometry("300x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="请选择要加载的配置:").pack(pady=10)
        
        listbox = tk.Listbox(dialog)
        listbox.pack(fill="both", expand=True, padx=10)
        for f in config_files:
            listbox.insert(tk.END, f)
        
        result = [None]  # 用列表存储结果，以便在内部函数中修改
        
        def on_select():
            if listbox.curselection():
                selected = listbox.get(listbox.curselection()[0])
                result[0] = os.path.join(self.config_dir, selected)
                dialog.destroy()
        
        ttk.Button(dialog, text="加载选中", command=on_select).pack(pady=10)
        
        self.root.wait_window(dialog)
        
        if result[0]:
            return self.load_config(result[0])
        else:
            return self.get_default_config()
    
    def load_config(self, file_path):
        """从文件加载配置"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 确保配置完整（补充缺失的键）
            default = self.get_default_config()
            for key in default:
                if key not in config:
                    config[key] = default[key]
            
            # 更新界面控件值
            self.router_ip_var.set(config["router_ip"])
            self.login_url_var.set(config["login_url"])
            self.start_page_var.set(config["start_page_url"])
            self.manage_url_var.set(config["manage_url"])
            self.username_var.set(config["username"])
            self.password_var.set(config["password"])
            self.interval_var.set(config["auto_interval"])
            self.interval_unit_var.set(config["interval_unit"])
                
            self.log(f"已加载配置: {os.path.basename(file_path)}")
            return config
        except Exception as e:
            self.log(f"加载配置失败: {str(e)}")
            messagebox.showerror("错误", f"加载配置失败: {str(e)}\n将使用默认配置")
            return self.get_default_config()
    
    def save_config(self):
        """保存配置并自动更新上次使用的配置"""
        # 更新配置字典
        self.config["router_ip"] = self.router_ip_var.get()
        self.config["login_url"] = self.login_url_var.get()
        self.config["start_page_url"] = self.start_page_var.get()
        self.config["manage_url"] = self.manage_url_var.get()
        self.config["username"] = self.username_var.get()
        self.config["password"] = self.password_var.get()
        self.config["auto_interval"] = self.interval_var.get()
        self.config["interval_unit"] = self.interval_unit_var.get()
        
        # 保存到上次使用的配置文件
        try:
            with open(self.last_used_config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            
            self.log("配置已保存")
            messagebox.showinfo("成功", "配置已保存")
            
            # 刷新配置列表
            self.refresh_config_list()
        except Exception as e:
            self.log(f"保存配置失败: {str(e)}")
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")
    
    def save_config_as(self):
        """另存为新的配置文件"""
        # 先更新当前配置
        self.config["router_ip"] = self.router_ip_var.get()
        self.config["login_url"] = self.login_url_var.get()
        self.config["start_page_url"] = self.start_page_var.get()
        self.config["manage_url"] = self.manage_url_var.get()
        self.config["username"] = self.username_var.get()
        self.config["password"] = self.password_var.get()
        self.config["auto_interval"] = self.interval_var.get()
        self.config["interval_unit"] = self.interval_unit_var.get()
        
        # 询问文件名
        default_name = f"config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filename = simpledialog.askstring("另存为", "请输入配置文件名:", initialvalue=default_name)
        
        if not filename:
            return
            
        if not filename.endswith('.json'):
            filename += '.json'
            
        file_path = os.path.join(self.config_dir, filename)
        
        # 检查文件是否存在
        if os.path.exists(file_path):
            if not messagebox.askyesno("确认覆盖", f"文件 {filename} 已存在，是否覆盖？"):
                return
        
        # 保存文件
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            
            self.log(f"配置已另存为: {filename}")
            messagebox.showinfo("成功", f"配置已另存为: {filename}")
            
            # 刷新配置列表
            self.refresh_config_list()
        except Exception as e:
            self.log(f"另存配置失败: {str(e)}")
            messagebox.showerror("错误", f"另存配置失败: {str(e)}")
    
    def reset_to_default(self):
        """恢复默认配置"""
        if messagebox.askyesno("确认", "确定要恢复默认配置吗？当前配置将被覆盖"):
            default_config = self.get_default_config()
            
            # 更新界面
            self.router_ip_var.set(default_config["router_ip"])
            self.login_url_var.set(default_config["login_url"])
            self.start_page_var.set(default_config["start_page_url"])
            self.manage_url_var.set(default_config["manage_url"])
            self.username_var.set(default_config["username"])
            self.password_var.set(default_config["password"])
            self.interval_var.set(default_config["auto_interval"])
            self.interval_unit_var.set(default_config["interval_unit"])
            
            # 更新WiFi列表
            self.config["wifi_list"] = default_config["wifi_list"]
            self.refresh_wifi_list()
            
            self.log("已恢复默认配置")
            messagebox.showinfo("成功", "已恢复默认配置")
    
    def refresh_config_list(self):
        """刷新配置文件列表"""
        self.config_listbox.delete(0, tk.END)
        
        # 获取所有配置文件
        if os.path.exists(self.config_dir):
            config_files = [f for f in os.listdir(self.config_dir) if f.endswith('.json')]
            for f in config_files:
                self.config_listbox.insert(tk.END, f)
    
    def load_selected_config(self):
        """加载选中的配置文件"""
        selected = self.config_listbox.curselection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个配置文件")
            return
            
        filename = self.config_listbox.get(selected[0])
        file_path = os.path.join(self.config_dir, filename)
        
        # 加载配置
        new_config = self.load_config(file_path)
        
        # 更新WiFi列表
        self.config["wifi_list"] = new_config["wifi_list"]
        self.refresh_wifi_list()
        
        # 更新当前配置
        self.config = new_config.copy()
        
        messagebox.showinfo("成功", f"已加载配置: {filename}")
    
    def delete_selected_config(self):
        """删除选中的配置文件"""
        selected = self.config_listbox.curselection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个配置文件")
            return
            
        filename = self.config_listbox.get(selected[0])
        
        # 保护默认配置和上次使用的配置
        if filename == "default.json":
            messagebox.showwarning("提示", "默认配置不能删除")
            return
            
        if messagebox.askyesno("确认删除", f"确定要删除配置文件 '{filename}' 吗？"):
            try:
                file_path = os.path.join(self.config_dir, filename)
                os.remove(file_path)
                self.log(f"已删除配置文件: {filename}")
                self.refresh_config_list()
                messagebox.showinfo("成功", f"已删除配置文件: {filename}")
            except Exception as e:
                self.log(f"删除配置文件失败: {str(e)}")
                messagebox.showerror("错误", f"删除配置文件失败: {str(e)}")
    
    # WiFi管理相关方法
    def refresh_wifi_list(self):
        self.wifi_listbox.delete(0, tk.END)
        if hasattr(self, 'config') and "wifi_list" in self.config:
            for wifi in self.config["wifi_list"]:
                self.wifi_listbox.insert(tk.END, wifi)
            
    def add_wifi(self):
        wifi_name = simpledialog.askstring("添加WiFi", "请输入WiFi名称，需连接过此wifi系统内保留的有密码，否则无法连接:")
        if wifi_name and wifi_name not in self.config["wifi_list"]:
            self.config["wifi_list"].append(wifi_name)
            self.refresh_wifi_list()
            self.log(f"已添加WiFi: {wifi_name}")
            
    def edit_wifi(self):
        selected = self.wifi_listbox.curselection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个WiFi")
            return
            
        old_name = self.wifi_listbox.get(selected[0])
        new_name = simpledialog.askstring("编辑WiFi", "请输入新的WiFi名称，需连接过此wifi系统内保留的有密码，否则无法连接，:", initialvalue=old_name)
        
        if new_name and new_name != old_name and new_name not in self.config["wifi_list"]:
            index = self.config["wifi_list"].index(old_name)
            self.config["wifi_list"][index] = new_name
            self.refresh_wifi_list()
            self.log(f"已将WiFi从 {old_name} 改为 {new_name}")
            
    def delete_wifi(self):
        selected = self.wifi_listbox.curselection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个WiFi")
            return
            
        wifi_name = self.wifi_listbox.get(selected[0])
        if messagebox.askyesno("确认", f"确定要删除WiFi '{wifi_name}' 吗?"):
            self.config["wifi_list"].remove(wifi_name)
            self.refresh_wifi_list()
            self.log(f"已删除WiFi: {wifi_name}")
    
    # 日志和UI更新相关方法
    def log(self, message):
        """添加日志到文本区域"""
        if self.log_text is None:
            return  # 日志控件尚未初始化时直接返回
        
        self.log_text.config(state="normal")
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)  # 滚动到最后
        self.log_text.config(state="disabled")
        
    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")
        self.log("日志已清空")
        
    def update_ascii_art(self):
        """更新ASCII艺术"""
        ascii_art = self.get_random_anime_ascii()
        self.ascii_label.config(text=ascii_art)
        self.root.after(5000, self.update_ascii_art)  # 5秒更新一次
        
    def get_random_anime_ascii(self):
        anime_ascii_list = [
            r"""
            --------------------
            /\__/\  
            (  ^_^ ) 
            / \/
            /  xx  \
            (___________)
            --------------------
            光猫重启助手启动中喵~
            """,
            r"""
            --------------------
            ####################
            #****************##
            #  █▀█ █▀█ █▀█  #
            #  █▄█ █▄█ █▄█  #
            #  [=]  <> [=]  #
            #****************##
            ####################
            --------------------
            """,
            r"""
            --------------------
            ██████------██████
            ██++++++++++++++██
            ██  █▀█ █▀█ █▀█ ██
            ██  █▄█ █▄█ █▄█ ██
            ██  ███ ███ ███ ██
            ██--------------██
            ██████+++++█████
            --------------------
            机甲模式：重启指令已发送
            """,
            """
            --------------------
            星空重启程序启动!
            正在连接光猫控制中心...
            --------------------
            """
        ]
        return random.choice(anime_ascii_list)
        
    def update_progress(self, value, message):
        """更新进度条和状态"""
        self.root.after(0, lambda: self.progress_var.set(value))
        self.root.after(0, lambda: self.progress_label.config(text=message))
    
    # 核心功能相关方法
    def start_reboot_thread(self):
        """启动重启线程"""
        self.reboot_btn.config(state="disabled")
        threading.Thread(target=self.reboot_router, daemon=True).start()
        
    def start_wifi_thread(self):
        """启动WiFi连接线程"""
        self.connect_wifi_btn.config(state="disabled")
        threading.Thread(target=self.connect_wifi, daemon=True).start()
        
    def reboot_router(self):
        """重启路由器的核心逻辑"""
        try:
            # 替换URL中的占位符
            router_ip = self.config["router_ip"]
            login_url = self.config["login_url"].format(router_ip=router_ip)
            start_page_url = self.config["start_page_url"].format(router_ip=router_ip)
            manage_url = self.config["manage_url"].format(router_ip=router_ip)
            username = self.config["username"]
            password = self.config["password"]
            
            self.log("开始重启光猫流程...")
            self.update_progress(10, "初始化浏览器...")
            
            driver = None
            try:
                chrome_options = webdriver.ChromeOptions()
                chrome_options.add_argument("--headless=new")
                chrome_options.add_argument("--window-size=1920,1080")
                chrome_options.add_argument("--log-level=0")
                
                if getattr(sys, 'frozen', False):
                    chromedriver_path = os.path.join(sys._MEIPASS, "chromedriver.exe")
                else:
                    chromedriver_path = os.path.join(os.path.dirname(__file__), "chromedriver.exe")
                
                if not os.path.exists(chromedriver_path):
                    raise FileNotFoundError(f"未找到Chrome驱动，请将chromedriver.exe放在以下目录：\n{os.path.dirname(chromedriver_path)}")
                
                service = Service(executable_path=chromedriver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
                self.update_progress(20, "浏览器已启动")
                
                self.log(f"已打开光猫登录页：{login_url}")
                driver.get(login_url)
                self.update_progress(30, "加载登录页面...")
                
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "role_user")),
                    message="登录页加载失败，未找到用户切换容器"
                )
                
                switch_user_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//td[@id='role_user']/a[@class='user' and @onclick=\"goPage('user');\"]")),
                    message="未找到普通用户切换按钮"
                )
                driver.execute_script("arguments[0].click();", switch_user_btn)
                self.log(f"已切换到普通用户：{username}")
                self.update_progress(40, "已切换用户类型")
                
                password_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "skypsd")),
                    message="未找到密码输入框"
                )
                password_field.clear()
                password_field.send_keys(password)
                self.log("已填写密码")
                self.update_progress(50, "已输入密码")
                
                login_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@type='submit' or @value='登录']")),
                    message="未找到登录按钮"
                )
                login_button.click()
                self.log("已提交登录请求")
                self.update_progress(60, "登录中...")
                
                WebDriverWait(driver, 15).until(
                    EC.url_contains(start_page_url),
                    message="登录失败，未跳转到默认页面"
                )
                self.log(f"登录成功，当前页面：{driver.current_url}")
                
                driver.get(manage_url)
                self.log(f"已进入重启页面：{manage_url}")
                self.update_progress(70, "进入重启管理页面")
                
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "Submit1")),
                    message="重启页面加载失败，未找到重启按钮"
                )
                
                reboot_button = driver.find_element(By.ID, "Submit1")
                driver.execute_script("arguments[0].click();", reboot_button)
                self.log("已点击【设备重启】按钮")
                self.update_progress(80, "已点击重启按钮")
                
                confirm_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "msgconfirmb")),
                    message="未找到重启确认按钮"
                )
                confirm_button.click()
                self.log("已点击【确定】按钮，重启指令已提交")
                self.update_progress(90, "确认重启指令")
                
                time.sleep(3)
                self.log("✅ 重启指令已发送，光猫将在5-15秒内重启")
                self.update_progress(100, "重启指令已发送")
                
            except Exception as e:
                self.log(f"❌ 操作失败：{str(e)}")
                self.update_progress(0, f"操作失败: {str(e)}")
            finally:
                if driver:
                    driver.quit()
                self.log("* 浏览器已关闭")
                
        finally:
            # 恢复按钮状态
            self.root.after(0, lambda: self.reboot_btn.config(state="normal"))
            # 5秒后重置进度条
            self.root.after(5000, lambda: self.update_progress(0, "准备就绪"))
            
    def connect_wifi(self):
        """连接WiFi的逻辑，返回连接状态"""
        try:
            if not self.config["wifi_list"]:
                self.log("❌ 未配置任何WiFi，请先在WiFi设置中添加")
                self.update_progress(0, "未配置WiFi")
                return False  # 返回连接失败状态
                
            self.log("开始连接WiFi...")
            self.update_progress(10, "开始连接WiFi...")
            total_wifi = len(self.config["wifi_list"])
            progress_step = 80 / total_wifi if total_wifi > 0 else 80
            connected = False  # 连接状态标记
            
            # 尝试连接每个WiFi
            for i, wifi in enumerate(self.config["wifi_list"]):
                current_progress = 10 + (i * progress_step)
                self.update_progress(current_progress, f"尝试连接: {wifi}")
                self.log(f"尝试连接WiFi: {wifi}")
                
                # 执行netsh命令
                result = subprocess.run(
                    f'netsh wlan connect name="{wifi}"',
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding='utf-8'
                )
                
                # 检查结果
                if result.returncode == 0:
                    self.log(f"✅ 成功连接到WiFi: {wifi}")
                    self.update_progress(100, f"已连接: {wifi}")
                    connected = True
                    break  # 连接成功则退出循环
                else:
                    error_msg = result.stderr.strip() or "连接失败"
                    self.log(f"❌ 连接WiFi {wifi} 失败: {error_msg}")
            
            # 所有WiFi都连接失败
            if not connected:
                self.log("❌ 所有配置的WiFi都连接失败")
                self.update_progress(0, "WiFi连接失败")
                
            return connected  # 返回最终连接状态
            
        finally:
            # 恢复按钮状态
            self.root.after(0, lambda: self.connect_wifi_btn.config(state="normal"))
            # 5秒后重置进度条
            self.root.after(5000, lambda: self.update_progress(0, "准备就绪"))
    
    # 定时任务相关方法
    def start_scheduled_task(self):
        """启动定时任务"""
        if self.scheduled_task_running:
            messagebox.showinfo("提示", "定时任务已在运行中")
            return
            
        interval = self.interval_var.get()
        unit = self.interval_unit_var.get()
        
        if interval < 1:
            messagebox.showwarning("警告", "时间间隔不能小于1")
            return
            
        # 保存配置的时间单位和间隔
        self.config["auto_interval"] = interval
        self.config["interval_unit"] = unit
        
        self.stop_event.clear()
        self.scheduled_task_running = True
        self.scheduled_task_thread = threading.Thread(target=self.scheduled_task_loop, daemon=True)
        self.scheduled_task_thread.start()
        
        # 更新UI状态
        self.start_schedule_btn.config(state="disabled")
        self.stop_schedule_btn.config(state="normal")
        self.status_var.set("运行中")
        self.status_label.config(foreground="green")
        
        # 计算下次运行时间（转换为秒）
        seconds = self.convert_to_seconds(interval, unit)
        next_run = datetime.now() + timedelta(seconds=seconds)
        self.next_run_var.set(next_run.strftime("%Y-%m-%d %H:%M:%S"))
        
        self.log(f"定时任务已启动，间隔 {interval} {unit}")
    
    def stop_scheduled_task(self):
        """停止定时任务"""
        if not self.scheduled_task_running:
            return
            
        self.stop_event.set()
        self.scheduled_task_running = False
        
        # 更新UI状态
        self.start_schedule_btn.config(state="normal")
        self.stop_schedule_btn.config(state="disabled")
        self.status_var.set("已停止")
        self.status_label.config(foreground="red")
        self.next_run_var.set("--")
        
        self.log("定时任务已停止")
    
    def convert_to_seconds(self, value, unit):
        """将时间值转换为秒"""
        if unit == "秒":
            return value
        elif unit == "分":
            return value * 60
        elif unit == "时":
            return value * 3600
        return value * 3600  # 默认小时
    
    def scheduled_task_loop(self):
        """定时任务循环"""
        try:
            while not self.stop_event.is_set():
                # 执行任务：先连接WiFi，再重启光猫
                self.log("===== 定时任务开始执行 =====")
                
                # 检查WiFi连接状态
                if self.connect_wifi():
                    self.log("WiFi连接成功，准备重启光猫...")
                    time.sleep(5)  # 等待网络稳定
                    self.reboot_router()
                else:
                    self.log("WiFi连接失败，取消本次重启操作")
                
                self.log("===== 定时任务执行完毕 =====")
                
                # 获取时间间隔（转换为秒）
                interval = self.config["auto_interval"]
                unit = self.config["interval_unit"]
                seconds = self.convert_to_seconds(interval, unit)
                
                # 计算下次运行时间
                next_run = datetime.now() + timedelta(seconds=seconds)
                self.root.after(0, lambda: self.next_run_var.set(next_run.strftime("%Y-%m-%d %H:%M:%S")))
                
                # 等待下一个周期
                self.log(f"等待{interval}{unit}后执行下一次任务...")
                self.stop_event.wait(seconds)
                
        finally:
            # 更新任务状态
            self.root.after(0, lambda: self.status_var.set("未运行"))
            self.root.after(0, lambda: self.start_schedule_btn.config(state="normal"))
            self.root.after(0, lambda: self.stop_schedule_btn.config(state="disabled"))

if __name__ == "__main__":
    # 确保中文显示正常
    root = tk.Tk()
    app = RouterRebootApp(root)
    root.mainloop()