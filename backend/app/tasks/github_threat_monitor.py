import datetime
import re
from lxml import etree
from app import utils
from app.utils.push import telegram_send, dingding_send
from app.config import Config

logger = utils.get_logger()

def get_github_headers():
    return {
        'Authorization': f"token {Config.GITHUB_TOKEN}" if Config.GITHUB_TOKEN else "",
        'Accept': 'application/vnd.github.v3+json'
    }

from app.utils.push import unified_push

class ThreatIntelligencePush:
    @staticmethod
    def push_msg(title, body):
        # Determine push_type from title
        if 'CVE' in title:
            push_type = 'github_cve'
        elif '工具' in title or '监控' in title:
            push_type = 'github_tools'
        elif '大佬' in title or '动态' in title:
            push_type = 'github_hackers'
        else:
            push_type = 'github_leak' # Fallback
            
        unified_push(push_type, title, body)

class GithubCveMonitorTask:
    def __init__(self):
        self.collection = "github_cve_history"
        
    def fetch_mitre_cve_desc(self, cve_id):
        try:
            url = f"https://cve.mitre.org/cgi-bin/cvename.cgi?name={cve_id}"
            res = utils.http_req(url, timeout=(10, 10))
            if res:
                html = etree.HTML(res.text)
                des = html.xpath('//*[@id="GeneratedTable"]/table//tr[4]/td/text()')[0].strip()
                return des
        except Exception as e:
            logger.warning(f"Fetch MITRE desc failed for {cve_id}: {e}")
        return "No description available on MITRE yet."

    def run(self):
        logger.info("Starting Github CVE Monitor Task...")
        year = datetime.datetime.now().year
        today_date = str(datetime.date.today())
        api = f"https://api.github.com/search/repositories?q=CVE-{year}&sort=updated&per_page=100"
        
        try:
            res = utils.http_req(api, headers=get_github_headers(), timeout=(10, 10))
            if not res or res.status_code != 200:
                logger.error("Failed to fetch Github repos for CVE.")
                return

            items = res.json().get('items', [])[:100]
            db = utils.conn_db(self.collection)

            for item in items:
                cve_name_raw = item['name'].upper()
                cve_match = re.findall(r'(CVE-\d+-\d+)', cve_name_raw)
                if not cve_match:
                    continue
                    
                cve_id = cve_match[0]
                pushed_at = ""
                try:
                    pushed_at = re.findall(r'\d{4}-\d{2}-\d{2}', item.get('pushed_at', ''))[0]
                except:
                    continue
                repo_url = item['html_url']

                if pushed_at != today_date:
                    continue

                if db.find_one({"cve_name": cve_id}):
                    continue 
                
                logger.info(f"New CVE found: {cve_id}")
                cve_desc = self.fetch_mitre_cve_desc(cve_id)
                
                title = f"🚨 发现新公开的 {cve_id} Github 利用代码！"
                body = (
                    f"**CVE 编号**: {cve_id}\n"
                    f"**项目地址**: {repo_url}\n"
                    f"**官方描述**: \n{cve_desc}\n"
                )
                ThreatIntelligencePush.push_msg(title, body)

                db.insert_one({
                    "cve_name": cve_id,
                    "cve_url": repo_url,
                    "pushed_at": today_date,
                    "desc": cve_desc,
                    "insert_time": utils.curr_date()
                })
                
        except Exception as e:
            logger.exception(f"GithubCveMonitorTask Error: {e}")


class GithubToolsMonitorTask:
    def __init__(self):
        self.collection = "github_tools_target"

    def run(self):
        logger.info("Starting Github Tools Monitor Task...")
        db = utils.conn_db(self.collection)
        targets = list(db.find({})) 
        
        for target in targets:
            repo_url = target.get('repo_url')
            if not repo_url: continue
                
            try:
                api_releases = f"{repo_url}/releases"
                res = utils.http_req(api_releases, headers=get_github_headers(), timeout=(10, 10))
                
                if res and res.status_code == 200 and len(res.json()) > 0:
                    latest = res.json()[0]
                    new_tag = latest.get('tag_name', '')
                    try:
                        new_pushed_at = re.findall(r'\d{4}-\d{2}-\d{2}', latest.get('published_at', ''))[0]
                    except:
                        new_pushed_at = ""
                    
                    old_tag = target.get('last_tag', '')
                    if new_tag != old_tag:
                        # 只有非首次监控（old_tag不为空）时，才推送更新通知
                        if old_tag != '':
                            update_log = latest.get('body', 'No update log provided.')
                            download_url = latest.get('html_url')
                            tool_name = repo_url.split('/')[-1]
                            
                            title = f"🛠️ 工具 [{tool_name}] 发布了新版本: {new_tag}"
                            body = f"**地址**: {download_url}\n**更新日志**:\n{update_log}"
                            
                            ThreatIntelligencePush.push_msg(title, body)
                            
                        # 无论是否首次，都更新数据库记录为最新版本
                        db.update_one({"_id": target["_id"]}, {"$set": {"last_tag": new_tag, "last_commit_time": new_pushed_at}})
            except Exception as e:
                logger.error(f"Failed to check tool {repo_url}: {e}")

class GithubHackersMonitorTask:
    def __init__(self):
        self.collection = "github_hackers_target"
        self.history_collection = "github_hackers_history" # 记录推送过的仓库，避免重复
        
    def run(self):
        logger.info("Starting Github Hackers Monitor Task...")
        db = utils.conn_db(self.collection)
        history_db = utils.conn_db(self.history_collection)
        
        targets = list(db.find({}))
        today_date = str(datetime.date.today())
        
        for target in targets:
            github_id = target.get('github_id')
            if not github_id: continue
                
            try:
                api = f"https://api.github.com/users/{github_id}/repos?sort=created&direction=desc"
                res = utils.http_req(api, headers=get_github_headers(), timeout=(10, 10))
                
                if not res or res.status_code != 200:
                    continue
                    
                repos = res.json()
                for repo in repos:
                    # 避免遍历太多，只看最近几条
                    if isinstance(repo, dict):
                        fork = repo.get('fork', False)
                        created_at_raw = repo.get('created_at', '')
                        if not created_at_raw: continue
                        
                        created_at = re.findall(r'\d{4}-\d{2}-\d{2}', created_at_raw)
                        if created_at and created_at[0] == today_date and not fork:
                            full_name = repo.get('full_name')
                            # 检查是否已推送
                            if not history_db.find_one({"full_name": full_name}):
                                name = repo.get('name')
                                description = repo.get('description') or "作者未写描述"
                                download_url = repo.get('html_url')
                                
                                title = f"👨‍💻 大佬 [{github_id}] 分享了一款新工具!"
                                body = (
                                    f"**工具名称**: {name}\n"
                                    f"**项目地址**: {download_url}\n"
                                    f"**工具描述**: {description}\n"
                                )
                                ThreatIntelligencePush.push_msg(title, body)
                                
                                history_db.insert_one({
                                    "full_name": full_name,
                                    "insert_time": utils.curr_date()
                                })
            except Exception as e:
                logger.error(f"Failed to check hacker {github_id}: {e}")

import time
LAST_RUN = {
    "cve": 0,
    "tools": 0,
    "hackers": 0
}

def threat_intelligence_scheduler():
    now = time.time()
    # CVE 抓取频率通过 DB 动态配置
    conf = utils.conn_db("system_config").find_one({"_id": "cve_radar_config"}) or {"enabled": False, "interval": 6}
    if conf.get("enabled", False):
        cve_interval_hours = conf.get("interval", 6)
        if now - LAST_RUN["cve"] > 3600 * cve_interval_hours:
            try:
                GithubCveMonitorTask().run()
            except Exception as e:
                logger.error(f"CVE schedule error: {e}")
            LAST_RUN["cve"] = now
        
    # Tools 抓取频率通过 DB 动态配置
    tools_conf = utils.conn_db("system_config").find_one({"_id": "tools_radar_config"}) or {"enabled": False, "interval": 6}
    if tools_conf.get("enabled", False):
        tools_interval_hours = tools_conf.get("interval", 6)
        if now - LAST_RUN["tools"] > 3600 * tools_interval_hours:
            try:
                GithubToolsMonitorTask().run()
            except Exception as e:
                logger.error(f"Tools schedule error: {e}")
            LAST_RUN["tools"] = now

    # Hackers 抓取频率通过 DB 动态配置
    hackers_conf = utils.conn_db("system_config").find_one({"_id": "hackers_radar_config"}) or {"enabled": False, "interval": 6}
    if hackers_conf.get("enabled", False):
        hackers_interval_hours = hackers_conf.get("interval", 6)
        if now - LAST_RUN["hackers"] > 3600 * hackers_interval_hours:
            try:
                GithubHackersMonitorTask().run()
            except Exception as e:
                logger.error(f"Hackers schedule error: {e}")
            LAST_RUN["hackers"] = now
