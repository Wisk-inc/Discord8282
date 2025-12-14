import requests, sys, json, uuid, time, os
from colorama import init, Fore, Back, Style

os.system('cls' if os.name=='nt' else 'clear')
init(autoreset=True)  # Initialize colorama
API="https://zefame-free.com/api_free.php?action=config"

names = {
    229: "TikTok Views",
    228: "TikTok Followers",
    232: "TikTok Free Likes",
    235: "TikTok Free Shares",
    236: "TikTok Free Favorites"
}

if len(sys.argv) > 1:
    with open(sys.argv[1]) as f:
        data = json.load(f)
else:
    data = requests.get("https://zefame-free.com/api_free.php?action=config").json()

services = data.get('data', {}).get('tiktok', {}).get('services', [])
for i, service in enumerate(services, 1):
    sid = service.get('id')
    name = names.get(sid, service.get('name', '').strip())
    rate = service.get('description', '').strip()
    if rate:
        rate = f"[{rate.replace('vues', 'views').replace('partages', 'shares').replace('favoris', 'favorites')}]"
    
    status = f"{Fore.GREEN}[WORKING]{Style.RESET_ALL}" if service.get('available') else f"{Fore.RED}[DOWN]{Style.RESET_ALL}"
    print(f"{i}. {name}  —  {status}  {Fore.CYAN}{rate}{Style.RESET_ALL}")
choice = input('Select number (Enter to exit): ').strip()
if not choice:
    sys.exit()

try:
    idx = int(choice)
    if idx < 1 or idx > len(services):
        print('Out of range')
        sys.exit()
except:
    print('Invalid')
    sys.exit()

selected = services[idx-1]
video_link = input('Enter video link: ')

id_check = requests.post("https://zefame-free.com/api_free.php?", data={"action": "checkVideoId", "link": video_link})
video_id = id_check.json().get("data", {}).get("videoId")
print("Parsed Video ID:", video_id)


print()

while True:
    order = requests.post("https://zefame-free.com/api_free.php?action=order", data={"service": selected.get('id'), "link": video_link, "uuid": str(uuid.uuid4()), "videoId": video_id})
    result = order.json()
    print(f"{Fore.GREEN}{json.dumps(result, separators=(',',':'))}{Style.RESET_ALL}")
    wait = result.get("data", {}).get("nextAvailable")
    if wait:
        try:
            wait = float(wait)
            if wait > time.time():
                time.sleep(wait - time.time() + 1)
        except:
            pass
