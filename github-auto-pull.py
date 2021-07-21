import os, hmac, hashlib, json, aiohttp
from quart import Quart, request, jsonify, make_response

app = Quart(__name__)
db_data = json.loads(open('github-auto-pull/data.json').read())

async def further_review(r):
    async with aiohttp.ClientSession() as session:
        async with session.post(db_data['webhook'], data=json.dumps({
        "content": "<@443217277580738571>",
        "embeds": [
            {
                "title": "Failed GitHub Hook",
                "description": f"**IP:** {r.headers['X-Forwarded-For']}\n**Method:** {r.method} to {r.full_path}\n\n**Headers:**\n```\n{r.headers}\n```",
                "color": 16723013
            }
          ]
        }), headers={"Content-Type": "application/json"}) as r:
            if r.status != 204:
                print(f"Failed to send webhook: {r.status}\n{await r.text()}")
    return await make_response(jsonify({"msg": "Invalid data provided. This request has been logged for further review."}), 403)

@app.route('/', methods=["POST"])
async def homepage():
    github_sha = request.headers["X-Hub-Signature-256"][7:]
    data = json.loads((await request.body).decode("utf-8"))
    repo_data = db_data[str(data['repository']['id'])]
    token = repo_data['token']
    signature = hmac.new(token.encode(), await request.body, hashlib.sha256).hexdigest()
    if github_sha != signature:
        return await further_review(request)

    os.system(f"git -C {repo_data['folder']} pull")
    if repo_data['pm2'] is not None:
        os.system(f"pm2 restart {repo_data['pm2']}")

    async with aiohttp.ClientSession() as session:
        async with session.post(db_data['webhook'], data=json.dumps({
        "embeds": [
            {
                "title": f"New Commit in {data['repository']['full_name']}",
                "description": data['head_commit']['message'],
                "url": data['head_commit']['url'],
                "color": 8311585,
                "author": {
                    "name": f"Committed by {data['sender']['login']}",
                    "url": data['sender']['html_url'],
                    "icon_url": data['sender']['avatar_url']
                }
            }
          ]
        }), headers={"Content-Type": "application/json"}) as r:
            if r.status != 204:
                print(f"Failed to send webhook: {r.status}\n{await r.text()}")
    return await make_response(jsonify({"success": True}), 200)

@app.errorhandler(Exception)
async def user_logging(e):
    return await further_review(request)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=11000, debug=False)
