#导入库
import sys
import subprocess
import importlib
import time
import pyautogui
import pytesseract
from PIL import Image
import keyboard
import cv2
import numpy as np
import pyautogui


def install_and_import(package):
    try:
        importlib.import_module(package)
        print(f"✅ {package} 库已安装")
    except ImportError:
        print(f"🔧 正在安装 {package} 库...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--user', package])
        print(f"🎉 {package} 安装成功，请重新运行本脚本")
        sys.exit(0)

# 自动安装 keyboard
install_and_import('keyboard')

# ===== 配置区域（请替换成你测量的坐标）=====
pytesseract.pytesseract.tesseract_cmd = r'F:\fkncai\tesseract.exe'

# ===== 左侧弹窗检测 =====
POPUP_CHECK_X = 102
POPUP_CHECK_Y = 502
EXPECTED_RGB_POPUP = (254, 242, 206)

# ===== 右侧弹窗检测 =====
VIEW_DETECTION_X = 1788
VIEW_DETECTION_Y = 309
EXPECTED_RGB_VIEW = (255, 247, 220)

# ===== 果实锁定检测 =====
FRUIT_CHECK_X = 402
FRUIT_CHECK_Y = 507
EXPECTED_RGB_FRUIT = (225, 152, 90)
   
# ===== 绿色/蓝色图标检测（区分作物/果实）=====
GREEN_ICON_X = 342
GREEN_ICON_Y = 494

# ===== 进度条检测（判断成熟）=====
percent_region = (187, 659, 310, 711)

# ===== 点击坐标（收获） =====
# 左侧弹窗中心
popup_click_x = 242
popup_click_y = 576

# 右侧收获按钮
harvest_x = 2119
harvest_y = 1193

# ---------- 背包清理相关坐标 ----------
examine_close_x, examine_close_y = 1029, 301
bag_icon_x, bag_icon_y = 2227, 174
select_all_x, select_all_y = 2148, 275
sell_btn_x, sell_btn_y = 2127, 1371
confirm_sell_x, confirm_sell_y = 1298, 1189
filter_x, filter_y = 336, 922   # “活动”提交按键坐标
# 有活动果实时的分支
submit_activity_x, submit_activity_y = 297, 946
auto_select_x, auto_select_y = 1590, 1306
confirm_submit_x, confirm_submit_y = 2148, 1300
close_shop_x, close_shop_y = 2467, 155
go_home_x, go_home_y = 96, 1087
# 无活动果实时的关闭背包按钮
close_bag_x, close_bag_y = 2418, 281

# 提交按键的颜色（二级提交弹窗按键的字体颜色）
ACTIVITY_RGB = (46, 41, 40)   # R,G,B


# ========== 全局运行标志 ==========
running = False   # 初始为暂停状态，需要按F2开始


# ========== 检测函数 ==========
def is_popup_visible():
    """通过固定点颜色判断左侧弹窗是否出现"""
    try:
        r, g, b = pyautogui.pixel(POPUP_CHECK_X, POPUP_CHECK_Y)
        # 允许一定误差（因为颜色可能轻微变化）
        if abs(r - EXPECTED_RGB_POPUP[0]) < 15 and \
           abs(g - EXPECTED_RGB_POPUP[1]) < 15 and \
           abs(b - EXPECTED_RGB_POPUP[2]) < 15:
            return True
        else:
            return False
    except:
        return False

def is_view_already_exists():
    """通过固定点固定色判断弹窗是否已经出现"""
    try:
        r, g, b = pyautogui.pixel(VIEW_DETECTION_X, VIEW_DETECTION_Y)
        if abs(r - EXPECTED_RGB_VIEW[0]) < 15 and \
           abs(g - EXPECTED_RGB_VIEW[1]) < 15 and \
           abs(b - EXPECTED_RGB_VIEW[2]) < 15:
            return True
        else:
            return False
    except:
        return False

def is_fruit_lock():
    '''判断果实是否是锁定的'''
    try:
        r, g, b = pyautogui.pixel(FRUIT_CHECK_X, FRUIT_CHECK_Y)
        if abs(r - EXPECTED_RGB_FRUIT[0]) < 3 and \
           abs(g - EXPECTED_RGB_FRUIT[1]) < 3 and \
           abs(b - EXPECTED_RGB_FRUIT[2]) < 3:
            return True
        else:
            return False
    except:
        return False
    
def is_plant_instead_of_fruit():
    try:
        r, g, b = pyautogui.pixel(GREEN_ICON_X, GREEN_ICON_Y)
        # 绿色范围
        if g == 200 and r == 115 and b == 255:
            return True
        # 蓝色范围
        if b == 69 and r == 80 and g == 163:
            return True
        return False
    except:
        return False

def is_mature_by_percent():
    left, top, right, bottom = percent_region
    width = right - left
    height = bottom - top
    img = pyautogui.screenshot(region=(left, top, width, height))
    # 可选：保存调试图片
    img.save('percent_debug1.png')
    text = pytesseract.image_to_string(img, config='--psm 8')
    print(f"百分比识别: '{text.strip()}'")
    return '%' not in text   # 没有%表示成熟

def find_template_on_screen(template_path, threshold=0.8, region=None):
    """
    在屏幕（或指定区域）上查找模板图片
    :param template_path: 模板图片路径
    :param threshold: 相似度阈值，0.7~0.9之间，越高越严格
    :param region: 可选，搜索区域 (left, top, width, height)
    :return: 如果找到返回 (x, y) 中心坐标，否则返回 None
    """
    # 加载模板
    template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
    if template is None:
        print(f"无法加载模板: {template_path}")
        return None
    w, h = template.shape[::-1]

    # 截图
    if region:
        screenshot = pyautogui.screenshot(region=region)
    else:
        screenshot = pyautogui.screenshot()
    screenshot_gray = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)

    # 模板匹配
    result = cv2.matchTemplate(screenshot_gray, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    #print(f"模板匹配最佳相似度: {max_val:.3f}")
    if max_val >= threshold:
        # 计算模板中心坐标
        center_x = (max_loc[0] + w // 2)
        center_y = (max_loc[1] + h // 2)
        if region:
            center_x += region[0]
            center_y += region[1]
        return (center_x, center_y)
    else:
        return None

def is_bag_full():
    """检测背包已满弹窗（使用模板匹配）"""
    # 只在整个屏幕中搜索“仓库”模板（也可以限定在屏幕上半部分，提高速度）
    # 注意：如果你知道弹窗大约出现的位置，可以传入 region 参数缩小搜索范围
    result = find_template_on_screen('storehouse_full.png', threshold=0.7)
    if result:
        print("检测到‘仓库’弹窗")
        return True
    else:
        return False

# ========== 操作函数 ==========
def perform_harvest():
    try:
        """执行收获操作（前提：左侧弹窗已出现，且当前选中的是成熟果实）"""
        if not is_view_already_exists():
            print("===检测到首轮收获 唤出右侧收获窗口===")
            # 点击左侧弹窗打开右侧详情
            pyautogui.click(popup_click_x, popup_click_y)
            time.sleep(0.5)
        # 点击收获按钮
        if is_view_already_exists():
            pyautogui.click(harvest_x, harvest_y)
            print(">>> 收获成功 <<<")
            time.sleep(0.5)
    except Exception as e:
        print(f"判断右侧窗口是否存在出错: {e}")

def handle_bag_full():
    print("检测到背包已满，开始自动清理")
    # 0.先点击其他地方关闭果实查看界面
    pyautogui.click(examine_close_x, examine_close_y)
    # 1. 点击背包图标
    pyautogui.click(bag_icon_x, bag_icon_y)
    time.sleep(1.0)
    # 2. 点击全选
    pyautogui.click(select_all_x, select_all_y)
    time.sleep(0.8)
    # 3. 点击出售
    pyautogui.click(sell_btn_x, sell_btn_y)
    time.sleep(0.8)
    # 4. 确认售卖弹窗
    pyautogui.click(confirm_sell_x, confirm_sell_y)
    time.sleep(1.0)

    # 5. 判断有无活动提交框
    try:
        r, g, b = pyautogui.pixel(filter_x, filter_y)
        # 如果颜色接近 NO_ACTIVITY_RGB，则无活动果实
        if abs(r - ACTIVITY_RGB[0]) < 3 and \
           abs(g - ACTIVITY_RGB[1]) < 3 and \
           abs(b - ACTIVITY_RGB[2]) < 3:
            print("有活动果实，执行提交流程")
            # 二级弹窗点击提交
            pyautogui.click(submit_activity_x, submit_activity_y)
            time.sleep(1)  # 等待传送
            # 商店界面：一键选择
            pyautogui.click(auto_select_x, auto_select_y)
            time.sleep(0.5)
            pyautogui.click(confirm_submit_x, confirm_submit_y)
            time.sleep(0.5)
            pyautogui.click(close_shop_x, close_shop_y)
            time.sleep(0.5)
            pyautogui.click(close_shop_x, close_shop_y)
            time.sleep(0.5)
            pyautogui.click(go_home_x, go_home_y)
            time.sleep(1)
            # 1. 点击背包图标
            pyautogui.click(bag_icon_x, bag_icon_y)
            time.sleep(1.0)
            # 2. 点击全选
            pyautogui.click(select_all_x, select_all_y)
            time.sleep(0.8)
            # 3. 点击出售
            pyautogui.click(sell_btn_x, sell_btn_y)
            time.sleep(0.8)
            # 4. 确认售卖弹窗
            pyautogui.click(confirm_sell_x, confirm_sell_y)
            time.sleep(1.0)
            pyautogui.click(close_bag_x, close_bag_y)
        else:
            print("无活动果实，直接关闭背包")
            pyautogui.click(close_bag_x, close_bag_y)
    except Exception as e:
        print(f"处理活动果实分支出错: {e}")

    print("背包清理完成")

# ========== 热键回调函数 ==========
def start_script():
    global running
    running = True
    print("\n【脚本已开始运行】")

def pause_script():
    global running
    running = False
    print("\n【脚本已暂停】")

# 注册全局热键
keyboard.add_hotkey('f2', start_script)
keyboard.add_hotkey('f4', pause_script)

# ========== 主程序 ==========
print("="*50)
print("自动收割脚本已启动（待机模式 + 全局热键）")
print("操作说明：")
print("  按 F2  → 开始自动收割")
print("  按 F4  → 暂停自动收割")
print("  按 ESC → 退出脚本")
print("="*50)
print("【当前状态：暂停】请手动对准果实后按 F2 开始")

# 用于防止重复收获的标记（记录上一次收获的时间，避免短时间内重复收获同一个）
last_harvest_time = 0
harvest_cooldown = 0.1   # 秒

while True:
    # 按 ESC 退出
    if keyboard.is_pressed('esc'):
        print("脚本已退出")
        break
    
    # 如果未开始，则休眠并跳过后续逻辑
    if not running:
        time.sleep(0.2)
        continue

    # 优先级最高：检查背包是否已满
    if is_bag_full():
        handle_bag_full()
        time.sleep(1)
        continue

    # 检测左侧弹窗是否出现,且果实是否锁定
    if is_popup_visible() and not is_fruit_lock():
        # 避免同一弹窗短时间内重复处理
        current_time = time.time()
        if current_time - last_harvest_time > harvest_cooldown:
            # 判断是否为果实且成熟
            if not is_plant_instead_of_fruit() and is_mature_by_percent():
                print("检测到成熟果实，自动收获")
                # 执行收获操作（不重复等待弹窗）
                perform_harvest()
                last_harvest_time = time.time()
            else:
                # 弹窗出现但不满足条件，可以短暂休眠避免高频检测
                time.sleep(0.5)
    else:
        # 无弹窗且且果实锁定时，短暂休眠降低CPU占用
        time.sleep(0.2)
