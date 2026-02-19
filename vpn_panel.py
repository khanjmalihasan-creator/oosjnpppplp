import requests
import json
import random
import string
from datetime import datetime, timedelta
import os

class XUIPanel:
    def __init__(self, config):
        self.base_url = config['base_url']
        self.username = config['username']
        self.password = config['password']
        self.inbound_id = config['inbound_id']
        self.session = requests.Session()
        self.login()
    
    def login(self):
        """ورود به پنل"""
        try:
            login_data = {
                'username': self.username,
                'password': self.password
            }
            response = self.session.post(
                f"{self.base_url}/login",
                data=login_data,
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
    
    def generate_client_id(self):
        """ساخت آیدی یکتا"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=24))
    
    def create_client(self, email, days=30):
        """ساخت کاربر جدید"""
        try:
            expiry_time = (datetime.now() + timedelta(days=days)).timestamp() * 1000
            
            client_data = {
                "id": self.inbound_id,
                "settings": json.dumps({
                    "clients": [{
                        "id": self.generate_client_id(),
                        "flow": "",
                        "email": email,
                        "limitIp": 0,
                        "totalGB": 0,
                        "expiryTime": int(expiry_time),
                        "enable": True,
                        "tgId": "",
                        "subId": ""
                    }]
                })
            }
            
            response = self.session.post(
                f"{self.base_url}/panel/api/inbounds/addClient",
                json=client_data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    config = self.get_client_config(email)
                    return {
                        'success': True,
                        'config': config,
                        'email': email
                    }
            
            return {'success': False, 'error': 'خطا در ساخت کاربر'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_client_config(self, email):
        """دریافت کانفیگ"""
        client_id = self.generate_client_id()
        domain = self.base_url.replace('http://', '').replace('https://', '').split(':')[0]
        
        return {
            'vless': f"vless://{client_id}@{domain}:443?path=%2F&security=tls&encryption=none&type=ws&host={domain}&sni={domain}#{email}",
            'vmess': f"vmess://{self.generate_vmess_config(email, client_id, domain)}",
            'trojan': f"trojan://{client_id}@{domain}:443?security=tls&type=ws&host={domain}#{email}"
        }
    
    def generate_vmess_config(self, email, client_id, domain):
        """ساخت کانفیگ vmess"""
        config = {
            "v": "2",
            "ps": email,
            "add": domain,
            "port": "443",
            "id": client_id,
            "aid": "0",
            "net": "ws",
            "type": "none",
            "host": domain,
            "path": "/",
            "tls": "tls"
        }
        import base64
        return base64.b64encode(json.dumps(config).encode()).decode()
