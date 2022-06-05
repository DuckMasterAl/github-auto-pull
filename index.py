import subprocess, hmac, hashlib, json, aiohttp, asyncio
from quart import Quart, request, abort

app = Quart(__name__)

async def send_message(message, disable_notification):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", headers={"Content-Type": "application/json"}, data=json.dumps({
            "chat_id": "",# << Replace with your Telegram chat id
            "text": message.replace(".", "\\.").replace("-", "\\-"),
            "disable_notification": disable_notification,
            "parse_mode": "MarkdownV2"
        })) as r:
            if r.status != 200:
                print(f"Failed to send to telegram ({r.status})")
                print(await r.json())
                return abort(500)

@app.before_serving
async def cache_token():
    global bot_token
    bot_token = (json.loads(open('data.json').read()))['bot_token']

@app.route('/', methods=['GET'])
async def index():
    return 'Hello, World!'

@app.route('/', methods=["POST"])
async def homepage():
    try:
        github_sha = request.headers["X-Hub-Signature-256"][7:]
        data = await request.json
        db_data = (json.loads(open('data.json').read()))[str(data['repository']['full_name'])]# Load json data and find the repo
        signature = hmac.new(db_data['token'].encode(), await request.body, hashlib.sha256).hexdigest()
        if github_sha != signature:
            return abort(403)
    except KeyError:
        return abort(403)

    if 'zen' in data:
        commit = "Initial request"
    else:
        commit = f"[{data['head_commit']['id'][:7]}]({data['head_commit']['url']})"

    if data['ref'] != "refs/heads/" + data['repository']['default_branch']:# Make sure this is a commit on the master branch
        return "", 204

    try:
        subprocess.run(f"git -C {db_data['folder']} pull", stderr=subprocess.PIPE, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        await send_message(f"*{data['repository']['full_name']}:* {commit}\nFailed to deploy successfully.\n\n```\n{e.stderr.decode()}\n```", False)
    else:
        await send_message(f"*{data['repository']['full_name']}:* {commit}\nReceived and deployed successfully.", True)

    if db_data['pm2'] is not None:
        subprocess.run(f"pm2 restart {db_data['pm2']}", shell=True)

    return "", 204

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=11000, debug=True)
