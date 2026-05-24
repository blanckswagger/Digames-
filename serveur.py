import asyncio
import websockets
import json
import os
import random

PORT = int(os.environ.get("PORT", 10000))

# salons[code] = {players, names, hands, turn, score, started}
salons = {}

def deal_hands():
    return [[1,2,3,4],[1,2,3,4],[1,2,3,4],[1,2,3,4]]

def new_code():
    while True:
        code = str(random.randint(10000000, 99999999))
        if code not in salons:
            return code

async def send_to(ws, data):
    try:
        await ws.send(json.dumps(data))
    except:
        pass

async def send_lobby(code):
    if code not in salons:
        return
    salon = salons[code]
    for ws, info in list(salon['players'].items()):
        await send_to(ws, {
            "type": "lobby_state",
            "players": salon['names'],
            "your_index": info['index']
        })

async def handler(ws):
    code = None
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except:
                continue
            t = msg.get("type")

            # CRÉER UN SALON
            if t == "create":
                name = msg.get("name", "J1")[:12]
                code = new_code()
                salons[code] = {
                    'players': {},
                    'names': [None]*4,
                    'hands': [[],[],[],[]],
                    'turn': 0,
                    'score': [0,0],
                    'started': False
                }
                salon = salons[code]
                salon['players'][ws] = {'index': 0, 'name': name}
                salon['names'][0] = name
                await send_to(ws, {
                    "type": "created",
                    "code": code,
                    "your_index": 0
                })
                await send_lobby(code)
                print(f"[+] Salon {code} créé par {name}")

            # REJOINDRE UN SALON
            elif t == "join":
                name = msg.get("name", "J?")[:12]
                join_code = msg.get("code", "").strip()
                if join_code not in salons:
                    await send_to(ws, {"type": "error", "msg": "Code salon invalide !"})
                    continue
                salon = salons[join_code]
                if salon['started']:
                    await send_to(ws, {"type": "error", "msg": "Partie déjà commencée !"})
                    continue
                idx = next((i for i in range(4) if salon['names'][i] is None), None)
                if idx is None:
                    await send_to(ws, {"type": "error", "msg": "Salon plein !"})
                    continue
                code = join_code
                salon['players'][ws] = {'index': idx, 'name': name}
                salon['names'][idx] = name
                await send_to(ws, {"type": "joined", "your_index": idx})
                await send_lobby(code)
                print(f"[+] {name} rejoint salon {code} (slot {idx+1})")

            # LANCER LA PARTIE
            elif t == "start":
                if code not in salons: continue
                salon = salons[code]
                if salon['players'][ws]['index'] != 0: continue
                if sum(1 for n in salon['names'] if n) < 4:
                    await send_to(ws, {"type": "error", "msg": "Pas assez de joueurs"}); continue
                salon['hands'] = deal_hands()
                salon['turn'] = 0
                salon['score'] = [0,0]
                salon['started'] = True
                for ws2, info in list(salon['players'].items()):
                    i = info['index']
                    await send_to(ws2, {
                        "type": "game_start",
                        "players": salon['names'],
                        "hand": salon['hands'][i],
                        "your_index": i,
                        "current_turn": 0,
                        "score": salon['score']
                    })
                print(f"[✓] Salon {code} — partie lancée !")

            # PASSER UNE CARTE
            elif t == "pass_card":
                if code not in salons: continue
                salon = salons[code]
                if not salon['started']: continue
                from_idx = salon['players'][ws]['index']
                if from_idx != salon['turn']:
                    await send_to(ws, {"type": "error", "msg": "Pas votre tour !"}); continue
                card = msg.get("card")
                if card not in salon['hands'][from_idx]:
                    await send_to(ws, {"type": "error", "msg": "Carte invalide"}); continue
                to_idx = (from_idx + 1) % 4
                salon['hands'][from_idx].remove(card)
                salon['hands'][to_idx].append(card)
                next_turn = (salon['turn'] + 1) % 4
                salon['turn'] = next_turn
                for ws2, info in list(salon['players'].items()):
                    i = info['index']
                    await send_to(ws2, {
                        "type": "card_passed",
                        "from_index": from_idx,
                        "to_index": to_idx,
                        "card": card,
                        "next_turn": next_turn,
                        "hand": salon['hands'][i],
                        "from_name": salon['names'][from_idx],
                        "to_name": salon['names'][to_idx]
                    })
                for i in range(4):
                    h = salon['hands'][i]
                    if len(h) == 4 and len(set(h)) == 1:
                        team = 0 if i in (0,2) else 1
                        salon['score'][team] += 1
                        for ws2 in list(salon['players']):
                            await send_to(ws2, {
                                "type": "win",
                                "winner_index": i,
                                "winner_name": salon['names'][i],
                                "team": team,
                                "score": salon['score']
                            })
                        salon['started'] = False
                        salon['hands'] = [[],[],[],[]]
                        print(f"[★] Salon {code} — {salon['names'][i]} gagne !")
                        break

            # REJOUER
            elif t == "rematch":
                if code not in salons: continue
                salon = salons[code]
                if salon['players'][ws]['index'] != 0: continue
                salon['hands'] = deal_hands()
                salon['turn'] = 0
                salon['started'] = True
                for ws2, info in list(salon['players'].items()):
                    i = info['index']
                    await send_to(ws2, {
                        "type": "game_start",
                        "players": salon['names'],
                        "hand": salon['hands'][i],
                        "your_index": i,
                        "current_turn": 0,
                        "score": salon['score']
                    })

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if code and code in salons:
            salon = salons[code]
            if ws in salon['players']:
                idx = salon['players'][ws]['index']
                salon['names'][idx] = None
                del salon['players'][ws]
                salon['started'] = False
                print(f"[-] J{idx+1} quitte salon {code}")
                await send_lobby(code)
            if not salon['players']:
                del salons[code]
                print(f"[x] Salon {code} supprimé")

async def main():
    print(f"DIGAMES serveur port {PORT}")
    async with websockets.serve(handler, "0.0.0.0", PORT):
        await asyncio.Future()

asyncio.run(main())
