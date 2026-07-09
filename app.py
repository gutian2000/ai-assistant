import streamlit as st
import os
import json
import hashlib
import requests
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


# =========================================================
# 1. 记忆系统
# =========================================================
class Memory:
    def __init__(self):
        self.data = {
            "最近查询的城市": [],
            "提醒事项": [],
            "对话历史": []
        }

    def add_city(self, city):
        if city not in self.data["最近查询的城市"]:
            self.data["最近查询的城市"].append(city)
            if len(self.data["最近查询的城市"]) > 5:
                self.data["最近查询的城市"] = self.data["最近查询的城市"][-5:]

    def get_recent_cities(self):
        return self.data["最近查询的城市"]

    def add_reminder(self, reminder):
        self.data["提醒事项"].append({
            "内容": reminder,
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        return f"✅ 已记住：{reminder}"

    def get_reminders(self):
        if not self.data["提醒事项"]:
            return "暂无提醒事项"
        result = "📋 你的提醒事项：\n"
        for i, item in enumerate(self.data["提醒事项"], 1):
            result += f"  {i}. {item['内容']}（记录于 {item['时间']}）\n"
        return result

    def get_context(self):
        context = ""
        if self.data["最近查询的城市"]:
            context += f"用户最近查询过这些城市：{', '.join(self.data['最近查询的城市'])}\n"
        if self.data["提醒事项"]:
            context += f"用户有 {len(self.data['提醒事项'])} 个待办提醒\n"
        return context


# =========================================================
# 2. 工具函数
# =========================================================

# 2.1 天气查询
def get_weather(city):
    API_KEY = os.getenv("AMAP_API_KEY")
    if not API_KEY:
        return "❌ 未配置高德地图API Key，请在.env文件中设置 AMAP_API_KEY"

    # 模拟数据兜底
    mock_weather = {
        "北京": "晴天，25°C，湿度40%",
        "上海": "多云，28°C，湿度65%",
        "广州": "雷阵雨，30°C，湿度80%",
        "深圳": "晴天，32°C，湿度70%",
        "杭州": "阴天，26°C，湿度60%",
        "成都": "小雨，24°C，湿度75%",
    }

    # 1. 获取城市 adcode (高德参数: address)
    geo_url = "https://restapi.amap.com/v3/geocode/geo"
    geo_params = {"key": API_KEY, "address": city, "output": "json"}

    try:
        geo_response = requests.get(geo_url, params=geo_params, timeout=5)
        geo_data = geo_response.json()

        if geo_data.get("status") != "1" or not geo_data.get("geocodes"):
            return f"【{city}】{mock_weather.get(city, '天气数据暂不可用，请稍后再试')}（当前使用模拟数据）"

        adcode = geo_data["geocodes"][0]["adcode"]
        city_name = geo_data["geocodes"][0]["city"]

        # 2. 查询实时天气 (高德参数: city)
        weather_url = "https://restapi.amap.com/v3/weather/weatherInfo"
        weather_params = {"key": API_KEY, "city": adcode, "output": "json"}
        weather_response = requests.get(weather_url, params=weather_params, timeout=5)
        weather_data = weather_response.json()

        if weather_data.get("status") != "1" or not weather_data.get("lives"):
            return f"【{city_name}】{mock_weather.get(city_name, '天气数据暂不可用')}（API返回异常，使用模拟数据）"

        live = weather_data["lives"][0]
        temp = int(live["temperature"])

        advice = "温度适宜"
        if temp >= 30:
            advice = "天气较热，注意防晒"
        elif temp >= 25:
            advice = "温度适宜"
        elif temp >= 20:
            advice = "天气温和"
        elif temp >= 10:
            advice = "天气偏凉，建议穿外套"
        else:
            advice = "天气寒冷，注意保暖"

        memory.add_city(city_name)

        return f"【{city_name}】{live['weather']}，{temp}°C，湿度{live['humidity']}%\n💡 {advice}"

    except Exception as e:
        return f"【{city}】{mock_weather.get(city, '天气服务暂时不可用，请稍后再试')}（当前使用模拟数据）"

# 2.2 快递查询
def track_package(tracking_number, carrier="顺丰"):
    KEY = os.getenv("KUAIDI100_KEY")
    CUSTOMER = os.getenv("KUAIDI100_CUSTOMER")
    if not KEY or not CUSTOMER:
        return "错误：未配置快递100授权参数"

    carrier_codes = {
        "顺丰": "shunfeng", "中通": "zhongtong", "圆通": "yuantong",
        "韵达": "yunda", "申通": "shentong", "邮政": "youzhengguonei",
        "京东": "jd", "德邦": "debang"
    }
    com = carrier_codes.get(carrier, "auto")

    param_json = json.dumps({"com": com, "num": tracking_number})
    sign_str = param_json + KEY + CUSTOMER
    sign = hashlib.md5(sign_str.encode()).hexdigest().upper()

    url = "https://poll.kuaidi100.com/poll/query.do"
    data = {"customer": CUSTOMER, "param": param_json, "sign": sign}

    try:
        resp = requests.post(url, data=data)
        result = resp.json()
        if result.get("status") == "200":
            info = result.get("data", [])
            if not info:
                return f"未找到单号 {tracking_number} 的物流信息"
            latest = info[0]
            status_map = {"0": "运输中", "1": "已揽收", "2": "派送中", "3": "已签收", "4": "问题件"}
            status_text = status_map.get(str(latest.get('status')), "运输中")
            reminder_map = {
                "运输中": "🚛 运输中，请耐心等待",
                "已揽收": "📮 已揽收，即将发出",
                "派送中": "🚚 派送中，请保持电话畅通",
                "已签收": "📦 已签收，请及时取件",
            }
            reminder = reminder_map.get(status_text, "请关注物流更新")
            return f"【{carrier}】{tracking_number}\n状态：{status_text}\n位置：{latest.get('context', '')}\n时间：{latest.get('time', '')}\n🔔 {reminder}"
        else:
            return f"查询失败：{result.get('message', '未知错误')}"
    except Exception as e:
        return f"查询快递失败：{e}"


# 2.3 计算器
def calculate(expression):
    try:
        allowed_chars = set("0123456789+-*/(). ")
        if not all(c in allowed_chars for c in expression):
            return "错误：表达式包含非法字符"
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误：{e}"


# 2.4 提醒管理
def manage_reminder(action, content=""):
    if action == "add" and content:
        return memory.add_reminder(content)
    elif action == "list":
        return memory.get_reminders()
    elif action == "delete":
        if memory.data["提醒事项"]:
            removed = memory.data["提醒事项"].pop()
            return f"✅ 已删除提醒：{removed['内容']}"
        return "没有可删除的提醒"
    else:
        return "支持操作：add（添加）、list（查看）、delete（删除）"


# =========================================================
# 3. Agent 引擎
# =========================================================
def process_user_input(user_input):
    """根据用户输入，调用对应的工具"""
    # 检测关键词并路由
    if any(city in user_input for city in ["北京", "上海", "广州", "深圳", "杭州", "成都"]):
        for city in ["北京", "上海", "广州", "深圳", "杭州", "成都"]:
            if city in user_input:
                return get_weather(city)

    if "计算" in user_input or any(op in user_input for op in ["+", "-", "*", "/"]):
        # 提取数学表达式
        import re
        match = re.search(r'[\d\+\-\*\/\(\)\.]+', user_input)
        if match:
            return calculate(match.group())

    if "快递" in user_input or "单号" in user_input:
        # 提取快递单号和公司
        import re
        # 简单提取
        words = user_input.split()
        tracking_num = None
        carrier = "顺丰"
        for word in words:
            if word.startswith("SF") or word.startswith("YT") or word.startswith("ZT"):
                tracking_num = word
            if word in ["顺丰", "中通", "圆通", "韵达", "申通"]:
                carrier = word
        if tracking_num:
            return track_package(tracking_num, carrier)
        else:
            return "请提供快递单号，例如：SF1234567890"

    if "提醒" in user_input and "记住" in user_input:
        content = user_input.replace("记住", "").replace("提醒", "").replace("我", "").replace("要", "").strip()
        if content:
            return memory.add_reminder(content)

    if "提醒" in user_input and ("查看" in user_input or "列表" in user_input or "什么" in user_input):
        return memory.get_reminders()

    if "删除" in user_input and "提醒" in user_input:
        if memory.data["提醒事项"]:
            removed = memory.data["提醒事项"].pop()
            return f"✅ 已删除提醒：{removed['内容']}"
        return "没有可删除的提醒"

    return "🤔 我可以帮你：查天气、查快递、计算、记提醒。试试说'北京天气'或'查顺丰 SF1234567890'"


# =========================================================
# 4. Streamlit 界面
# =========================================================

# 初始化记忆
if "memory" not in st.session_state:
    st.session_state.memory = Memory()
    st.session_state.messages = []

# 让工具函数能访问 session_state 中的 memory
global memory
memory = st.session_state.memory

st.set_page_config(page_title="智能工作助理", page_icon="🤖", layout="wide")

# 侧边栏
with st.sidebar:
    st.title("🤖 智能工作助理")
    st.markdown("---")
    st.markdown("### 📌 支持功能")
    st.markdown("""
    - ☀️ 天气查询（真实API）
    - 📦 快递查询（真实API）
    - 🧮 数学计算
    - 📝 提醒管理
    """)
    st.markdown("---")
    st.markdown("### 💡 示例指令")
    st.markdown("""
    - `北京天气`
    - `查顺丰 SF1234567890`
    - `计算 100+200`
    - `记住我要买牛奶`
    - `查看提醒`
    - `删除提醒`
    """)
    st.markdown("---")
    if st.button("🗑️ 清空对话"):
        st.session_state.messages = []
        st.rerun()

# 主界面
st.title("🤖 智能工作助理")
st.caption("支持：天气查询 · 快递查询 · 计算器 · 提醒管理")

# 显示聊天历史
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入框
if prompt := st.chat_input("请输入你的问题..."):
    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 处理并显示回复
    with st.chat_message("assistant"):
        with st.spinner("🤔 正在思考..."):
            response = process_user_input(prompt)
            st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})