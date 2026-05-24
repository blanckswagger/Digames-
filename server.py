import asyncio
import websockets
import json
import os
import random

PORT = int(os.environ.get("PORT", 10000))

players = {}
names = [None]*4
hands = [[], [], [], []]
current_turn = 0
score = [0, 0]
game_started = False

def deal_hands():
    # Chaque joueur reçoit exactement 1,2,3,4
    return [[1,2,3,4],[1,2,3,4],[1,2,3,4],[1,2,3,4]]

async def send_to(ws, data):
    try:
        await ws.send(json.dumps(data))
    except:
        pass

async def send_lobby():
    for ws, info in list(players.items()):
        await send_to(ws, {"type":"lobby_state","players":names,"your_index":info["index"]})

async def handler(ws):
    global game_started, current_turn, score, hands, names
    idx = next((i for i in range(4) if names[i] is None), None)
    if idx is None:
        await send_to(ws, {"type":"error","msg":"Salle pleine !"}); return
    players[ws] = {"index":idx,"name":""}
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except:
                continue
            t = msg.get("type")
            if t == "join":
                name = msg.get("name","J"+str(idx+1))[:12]
                players[ws]["name"] = name
                names[idx] = name
                await send_lobby()
                if idx == 0:
                    await send_to(ws, {"type":"you_are_host"})
            elif t == "start":
                if players[ws]["index"] != 0: continue
                if sum(1 for n in names if n) < 4:
                    await send_to(ws,{"type":"error","msg":"Pas assez de joueurs"}); continue
                hands = deal_hands()
                current_turn = 0
                score = [0,0]
                game_started = True
                for ws2,info in list(players.items()):
                    i = info["index"]
                    await send_to(ws2,{"type":"game_start","players":names,"hand":hands[i],"your_index":i,"current_turn":0,"score":score})
            elif t == "pass_card":
                if not game_started: continue
                from_idx = players[ws]["index"]
                if from_idx != current_turn:
                    await send_to(ws,{"type":"error","msg":"Pas votre tour !"}); continue
                card = msg.get("card")
                if card not in hands[from_idx]:
                    await send_to(ws,{"type":"error","msg":"Carte invalide"}); continue
                # Sens horaire : 0->1->2->3->0
                to_idx = (from_idx + 1) % 4
                hands[from_idx].remove(card)
                hands[to_idx].append(card)
                next_turn = (current_turn + 1) % 4
                current_turn = next_turn
                for ws2,info in list(players.items()):
                    i = info["index"]
                    await send_to(ws2,{"type":"card_passed","from_index":from_idx,"to_index":to_idx,"card":card,"next_turn":next_turn,"hand":hands[i],"from_name":names[from_idx],"to_name":names[to_idx]})
                for i in range(4):
                    h = hands[i]
                    if len(h)==4 and len(set(h))==1:
                        team = 0 if i in (0,2) else 1
                        score[team] += 1
                        for ws2 in list(players):
                            await send_to(ws2,{"type":"win","winner_index":i,"winner_name":names[i],"team":team,"score":score})
                        game_started = False
                        hands = [[],[],[],[]]
                        break
            elif t == "rematch":
                if players[ws]["index"] != 0: continue
                hands = deal_hands()
                current_turn = 0
                game_started = True
                for ws2,info in list(players.items()):
                    i = info["index"]
                    await send_to(ws2,{"type":"game_start","players":names,"hand":hands[i],"your_index":i,"current_turn":0,"score":score})
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if ws in players:
            names[players[ws]["index"]] = None
            del players[ws]
            game_started = False
            await send_lobby()

async def main():
    print(f"DIGAMES serveur port {PORT}")
    async with websockets.serve(handler, "0.0.0.0", PORT):
        await asyncio.Future()

asyncio.run(main())
