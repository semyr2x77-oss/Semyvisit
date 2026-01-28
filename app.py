from fastapi import FastAPI
import asyncio
import aiohttp
import json
from byte import encrypt_api, Encrypt_ID
from visit_count_pb2 import Info

app = FastAPI()


# ---------------------------------------------------
# Load tokens by region
# ---------------------------------------------------
def load_tokens(region: str):
    try:
        region = region.upper()
        if region == "IND":
            path = "token_ind.json"
        elif region in {"BR", "US", "SAC", "NA"}:
            path = "token_br.json"
        else:
            path = "token_bd.json"

        with open(path, "r") as f:
            data = json.load(f)

        return [item["token"] for item in data if item.get("token")]
    except:
        return []


# ---------------------------------------------------
# Server URLs
# ---------------------------------------------------
def get_url(region: str):
    region = region.upper()

    if region == "IND":
        return "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
    elif region in {"BR", "US", "SAC", "NA"}:
        return "https://client.us.freefiremobile.com/GetPlayerPersonalShow"

    return "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"


# ---------------------------------------------------
# Parse protobuf response
# ---------------------------------------------------
def parse_proto(data):
    try:
        info = Info()
        info.ParseFromString(data)
        return {
            "uid": info.AccountInfo.UID,
            "nickname": info.AccountInfo.PlayerNickname,
            "likes": info.AccountInfo.Likes,
            "region": info.AccountInfo.PlayerRegion,
            "level": info.AccountInfo.Levels
        }
    except:
        return None


# ---------------------------------------------------
# Visit function
# ---------------------------------------------------
async def visit(session, url, token, uid, data):
    headers = {
        "ReleaseVersion": "OB52",
        "X-GA": "v1 1",
        "Authorization": f"Bearer {token}",
        "Host": url.split('/')[2]
    }

    try:
        async with session.post(url, headers=headers, data=data, ssl=False) as r:
            if r.status == 200:
                return True, await r.read()
            return False, None
    except:
        return False, None


# ---------------------------------------------------
# MAIN 1000 VISIT ENGINE
# ---------------------------------------------------
async def run_visit(uid, region):
    tokens = load_tokens(region)
    if not tokens:
        return None, 0

    url = get_url(region)
    encrypted = encrypt_api("08" + Encrypt_ID(str(uid)) + "1801")
    data = bytes.fromhex(encrypted)

    success = 0
    first_info = None

    connector = aiohttp.TCPConnector(limit=0)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            visit(session, url, tokens[i % len(tokens)], uid, data)
            for i in range(1000)
        ]

        results = await asyncio.gather(*tasks)

        for ok, resp in results:
            if ok:
                success += 1
                if not first_info:
                    first_info = parse_proto(resp)

    return first_info, success


# ---------------------------------------------------
# FASTAPI ROUTE
# ---------------------------------------------------
@app.get("/{region}/{uid}")
async def visit_api(region: str, uid: int):

    info, ok = await run_visit(uid, region)

    if not info:
        return {
            "status": "error",
            "message": "Failed to fetch profile"
        }

    return {
        "status": "success",
        "profile": info,
        "success": ok,
        "failed": 1000 - ok
    }