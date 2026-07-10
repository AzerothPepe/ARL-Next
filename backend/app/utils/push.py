import time
import base64
import hmac
import urllib.parse
import hashlib
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.utils import http_req, get_logger
from app.config import Config

logger = get_logger()


class Push(object):
    """docstring for ClassName"""

    def __init__(self, asset_map, asset_counter):
        super(Push, self).__init__()
        self.asset_map = asset_map
        self.asset_counter = asset_counter
        self._domain_info_list = None
        self._site_info_list = None
        self._ip_info_list = None
        self.domain_len = self.asset_counter.get("domain", 0)
        self.ip_len = self.asset_counter.get("ip", 0)
        self.site_len = self.asset_counter.get("site", 0)
        self.task_name = self.asset_map.get("task_name", "")

    @property
    def domain_info_list(self):
        if self._domain_info_list is None:
            self._domain_info_list = self.build_domain_info_list()

        return self._domain_info_list

    @property
    def site_info_list(self):
        if self._site_info_list is None:
            self._site_info_list = self.build_site_info_list()

        return self._site_info_list

    @property
    def ip_info_list(self):
        if self._ip_info_list is None:
            self._ip_info_list = self.build_ip_info_list()

        return self._ip_info_list

    def build_domain_info_list(self):
        if "domain" not in self.asset_map:
            return []
        domain_info_list = []
        for old in self.asset_map["domain"]:
            domain_dict = dict()
            domain_dict["域名"] = old["domain"]
            domain_dict["解析类型"] = old["type"]
            domain_dict["记录值"] = old["record"][0]
            domain_info_list.append(domain_dict)

        return domain_info_list

    def build_ip_info_list(self):
        if "ip" not in self.asset_map:
            return []
        ip_info_list = []
        for old in self.asset_map["ip"]:
            ip_dict = dict()
            port_list = []
            for port_info in old["port_info"]:
                port_list.append(str(port_info["port_id"]))

            ip_dict["IP"] = old["ip"]
            ip_dict["端口数目"] = len(port_list)
            ip_dict["开放端口"] = ",".join(port_list[:10])
            ip_dict["组织"] = old["geo_asn"].get("organization")
            ip_info_list.append(ip_dict)

        return ip_info_list

    def build_site_info_list(self):
        if "site" not in self.asset_map:
            return []
        site_info_list = []
        for old in self.asset_map["site"]:
            site_dict = dict()
            site_dict["站点"] = old["site"]
            site_dict["标题"] = old["title"]
            site_dict["状态码"] = old["status"]
            site_dict["favicon"] = old["favicon"].get("hash", "")
            site_info_list.append(site_dict)
        return site_info_list

    def _push_dingding(self):
        tpl = ""
        if self.domain_len > 0:
            tpl = "[{}]新发现域名 `{}` , 站点 `{}`\n***\n".format(self.task_name, self.domain_len, self.site_len)
            tpl = "{}\n{}".format(tpl, dict2dingding_mark(self.domain_info_list))

        if self.ip_len > 0:
            tpl = "[{}]新发现 IP `{}` , 站点 `{}`\n***\n".format(self.task_name, self.ip_len, self.site_len)
            tpl = "{}\n{}".format(tpl, dict2dingding_mark(self.ip_info_list))

        tpl += "\n***\n"
        tpl = "{}\n{}".format(tpl, dict2dingding_mark(self.site_info_list))
        ding_out = dingding_send(msg=tpl, access_token=Config.DINGDING_ACCESS_TOKEN,
                                 secret=Config.DINGDING_SECRET, msgtype="markdown")
        if ding_out["errcode"] != 0:
            logger.warning("发送失败 \n{}\n {}".format(tpl, ding_out))
            return False
        return True

    def _push_wx_work(self):
        tpl = ""
        if self.domain_len > 0:
            tpl = "[{}]新发现域名 `{}` , 站点 `{}`\n".format(self.task_name, self.domain_len, self.site_len)
            tpl = "{}\n{}".format(tpl, dict2dingding_mark(self.domain_info_list))

        if self.ip_len > 0:
            tpl = "[{}]新发现 IP `{}` , 站点 `{}`\n".format(self.task_name, self.ip_len, self.site_len)
            tpl = "{}\n{}".format(tpl, dict2dingding_mark(self.ip_info_list))

        tpl += "\n"
        tpl = "{}\n{}".format(tpl, dict2dingding_mark(self.site_info_list))
        ding_out = wx_work_send(msg=tpl, webhook_url=Config.WX_WORK_WEBHOOK)
        if ding_out["errcode"] != 0:
            logger.warning("发送失败 \n{}\n {}".format(tpl, ding_out))
            return False
        return True

    def _push_feishu(self):
        tpl = ""
        if self.domain_len > 0:
            tpl = "[{}]新发现域名 {}, 站点 {}\n".format(self.task_name, self.domain_len, self.site_len)
            tpl = "{}{}".format(tpl, dict2dingding_mark(self.domain_info_list))

        if self.ip_len > 0:
            tpl = "[{}]新发现 IP {}, 站点{}\n".format(self.task_name, self.ip_len, self.site_len)
            tpl = "{}{}".format(tpl, dict2dingding_mark(self.ip_info_list))

        tpl = "{}\n{}".format(tpl, dict2dingding_mark(self.site_info_list))
        feishu_out = feishu_send(msg=tpl, webhook_url=Config.FEISHU_WEBHOOK,
                                 secret=Config.FEISHU_SECRET)
        if feishu_out["code"] != 0:
            logger.warning("发送失败 \n{}\n {}".format(tpl[:50], feishu_out))
            return False
        return True

    def _push_telegram(self):
        tpl = ""
        if self.domain_len > 0:
            tpl = "[{}]新发现域名 {}, 站点 {}\n".format(self.task_name, self.domain_len, self.site_len)
            tpl = "{}{}".format(tpl, dict2dingding_mark(self.domain_info_list))

        if self.ip_len > 0:
            tpl = "[{}]新发现 IP {}, 站点{}\n".format(self.task_name, self.ip_len, self.site_len)
            tpl = "{}{}".format(tpl, dict2dingding_mark(self.ip_info_list))

        tpl = "{}\n{}".format(tpl, dict2dingding_mark(self.site_info_list))
        try:
            telegram_send(f"*{self.task_name}*\n\n{tpl}", bot_token=Config.TG_BOT_TOKEN, chat_id=Config.TG_CHAT_ID)
            return True
        except Exception as e:
            logger.warning("Telegram发送失败 \n{}\n {}".format(tpl[:50], str(e)))
            return False

    def _push_email(self):
        html = ""
        if self.domain_len > 0:
            tpl = "<div> 新发现域名 {}, 站点 {}\n</div>".format(self.domain_len, self.site_len)
            html = tpl
            html += "<br/>"
            html += dict2table(self.domain_info_list)

        if self.ip_len > 0:
            tpl = "<div> 新发现 IP {}, 站点 {}\n</div>".format(self.ip_len, self.site_len)
            html = tpl
            html += "<br/>"
            html += dict2table(self.ip_info_list)

        html += "<br/><br/>"
        html += dict2table(self.site_info_list)

        title = "[{}] 灯塔消息推送".format(self.task_name[:50])
        send_email(host=Config.EMAIL_HOST, port=Config.EMAIL_PORT, mail=Config.EMAIL_USERNAME,
                   password=Config.EMAIL_PASSWORD, to=Config.EMAIL_TO, title=title, html=html)

        return True

    def push_dingding(self):
        try:
            if Config.DINGDING_ACCESS_TOKEN and Config.DINGDING_SECRET:
                if self._push_dingding():
                    logger.info("push dingding succ")
                    return True

        except Exception as e:
            logger.warning(f"[{self.task_name}] push dingding error: {e}")

    def push_email(self):
        try:
            if Config.EMAIL_HOST and Config.EMAIL_USERNAME and Config.EMAIL_PASSWORD:
                self._push_email()
                logger.info("send email succ")
                return True
        except Exception as e:
            logger.warning(f"[{self.task_name}] push email error: {e}")

    def push_feishu(self):
        try:
            if Config.FEISHU_WEBHOOK and Config.FEISHU_SECRET:
                self._push_feishu()
                logger.info("send feishu succ")
                return True
        except Exception as e:
            logger.warning(f"[{self.task_name}] push feishu error: {e}")

    def push_wx_work(self):
        try:
            if Config.WX_WORK_WEBHOOK:
                self._push_wx_work()
                logger.info("send wx work succ")
                return True
        except Exception as e:
            logger.warning(f"[{self.task_name}] push wx work error: {e}")

    def push_telegram(self):
        try:
            if getattr(Config, 'TG_BOT_TOKEN', None) and getattr(Config, 'TG_CHAT_ID', None):
                self._push_telegram()
                logger.info("send telegram succ")
                return True
        except Exception as e:
            logger.warning(f"[{self.task_name}] push telegram error: {e}")


def message_push(asset_map, asset_counter):
    if "task_complete" not in Config.PUSH_OPTIONS:
        return
    logger.info("ARL push run")
    p = Push(asset_map=asset_map, asset_counter=asset_counter)
    p.push_dingding()
    p.push_email()
    p.push_feishu()
    p.push_wx_work()
    p.push_telegram()

def unified_push(push_type: str, title: str, content: str):
    """
    统一消息推送入口，适配所有配置的有效渠道
    """
    if push_type not in Config.PUSH_OPTIONS:
        return
        
    # 钉钉
    if Config.DINGDING_ACCESS_TOKEN and Config.DINGDING_SECRET:
        try:
            dingding_send(content, Config.DINGDING_ACCESS_TOKEN, Config.DINGDING_SECRET, msgtype="markdown", title=title)
        except Exception as e:
            logger.warning(f"unified_push dingding error: {e}")
            
    # 飞书
    if Config.FEISHU_WEBHOOK and Config.FEISHU_SECRET:
        try:
            feishu_send(content, Config.FEISHU_WEBHOOK, Config.FEISHU_SECRET, title=title)
        except Exception as e:
            logger.warning(f"unified_push feishu error: {e}")
            
    # 企业微信
    if Config.WX_WORK_WEBHOOK:
        try:
            wx_content = f"**{title}**\n\n{content}"
            wx_work_send(wx_content, Config.WX_WORK_WEBHOOK)
        except Exception as e:
            logger.warning(f"unified_push wx_work error: {e}")
            
    # 邮件
    if Config.EMAIL_HOST and Config.EMAIL_USERNAME and Config.EMAIL_PASSWORD and Config.EMAIL_TO:
        try:
            html = content.replace('\n', '<br>')
            html = f"<div><h3>{title}</h3><div>{html}</div></div>"
            send_email(Config.EMAIL_HOST, Config.EMAIL_PORT, Config.EMAIL_USERNAME, Config.EMAIL_PASSWORD, Config.EMAIL_TO, title, html)
        except Exception as e:
            logger.warning(f"unified_push email error: {e}")

    # Telegram
    tg_token = getattr(Config, 'TG_BOT_TOKEN', None)
    tg_chat = getattr(Config, 'TG_CHAT_ID', None)
    if tg_token and tg_chat:
        try:
            telegram_send(f"*{title}*\n\n{content}", tg_token, tg_chat)
        except Exception as e:
            logger.warning(f"unified_push telegram error: {e}")


def dict2dingding_mark(info_list):
    if not info_list:
        return ""

    title_tpl = '  \t\t  '.join(map(str, info_list[0].keys()))
    items_tpl = ""
    cnt = 0
    for row in info_list:
        cnt += 1
        row = ' \t '.join(map(str, row.values()))
        items_tpl += "{}. {}\n".format(cnt, row)

    return "{}\n{}".format(title_tpl, items_tpl)


def dingding_send(msg, access_token, secret, msgtype="text", title="灯塔消息推送"):
    ding_url = "https://oapi.dingtalk.com/robot/send?access_token={}".format(access_token)
    timestamp = str(round(time.time() * 1000))
    secret_enc = secret.encode('utf-8')
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    param = "&timestamp={}&sign={}".format(timestamp, sign)
    ding_url = ding_url + param
    send_json = {
        "msgtype": msgtype,
        "text": {
            "content": msg
        },
        "markdown": {
            "title": title,
            "text": msg
        }
    }
    conn = http_req(ding_url, method='post', json=send_json)
    return conn.json()


def send_email(host, port, mail, password, to, title, html, smtp_timeout=10):
    context = ssl.create_default_context()
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, context=context, timeout=smtp_timeout)
    else:
        server = smtplib.SMTP(host, port, timeout=smtp_timeout)

    msg = MIMEMultipart()
    msg['Subject'] = title
    msg['From'] = mail
    msg['To'] = to
    part1 = MIMEText(html, "html", "utf-8")
    msg.attach(part1)
    server.login(mail, password)
    server.send_message(msg)
    server.close()


def dict2table(info_list):
    if not info_list:
        return ""
    html = ""
    table_style = 'style="border-collapse: collapse;"'
    table_start = '<table {}>\n'.format(table_style)
    table_end = '</table>\n'
    style = 'style="border: 0.5pt solid windowtext;"'
    thead_start = '<thead><tr><th {}>序号</th><th {}>\n'.format(style, style)
    thead_end = '\n</th></tr></thead>'
    th_join_tpl = '</th>\n<th {}>'.format(style)
    thead_tpl = th_join_tpl.join(map(str, info_list[0].keys()))
    html += table_start
    html += thead_start
    html += thead_tpl
    html += thead_end

    tbody = "<tbody>\n"
    cnt = 0
    for row in info_list:
        cnt += 1
        td_join_tpl = '</td>\n<td {}>'.format(style)
        row_start = '<tr><td {}>{}</td>\n<td {}>'.format(style, cnt, style)
        items = [str(x).replace('>', "&#x3e;").replace('<', "&#x3c;") for x in row.values()]
        row = td_join_tpl.join(items)
        row_end = '</td>\n</tr>'
        row_tpl = row_start + row + row_end
        tbody = tbody + row_tpl + "\n"

    html = html + tbody + "</tbody>" + table_end

    return html


def feishu_send(msg, webhook_url, secret, title="灯塔消息推送"):
    timestamp = str(int(time.time()))
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    # 对结果进行base64处理
    sign = base64.b64encode(hmac_code).decode('utf-8')

    send_data = {
        "timestamp": timestamp,
        "sign": sign,
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": [
                        [{
                            "tag": "text",
                            "text": msg
                        }]
                    ]
                }
            }
        }
    }
    conn = http_req(webhook_url, method='post', json=send_data)
    return conn.json()


def wx_work_send(msg, webhook_url):
    send_data = {
        "msgtype": "markdown",
        "markdown":{
            "content": msg
        }
    }
    conn = http_req(webhook_url, method='post', json=send_data)
    return conn.json()

def telegram_send(msg, bot_token, chat_id):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "Markdown"
    }
    try:
        conn = http_req(url, method='post', json=payload, timeout=10)
        return conn.json()
    except Exception as e:
        logger.warning(f"telegram_send error: {e}")
        return {}
