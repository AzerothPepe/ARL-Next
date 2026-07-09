from app.services.dns_query import DNSQueryBase
from app import utils


class Query(DNSQueryBase):
    def __init__(self):
        super(Query, self).__init__()
        self.source_name = "alienvault"
        self.api_url = "https://otx.alienvault.com/"

    def sub_domains(self, target):
        url = "{}api/v1/indicators/domain/{}/passive_dns".format(self.api_url, target)
        try:
            response = utils.http_req(url, 'get', timeout=(30.1, 50.1))
            items = response.json()
        except Exception as e:
            self.logger.warning(f"AlienVault request/json error for {target}: {e}")
            return []

        results = []
        if isinstance(items, dict) and "passive_dns" in items:
            for item in items.get("passive_dns", []):
                hostname = item.get("hostname")
                if hostname:
                    results.append(hostname)

        return list(set(results))

