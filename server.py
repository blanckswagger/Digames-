import asyncio
import websockets
import json
import os
import random

PORT = int(os.environ.get("PORT", 10000))

salons = {}

# ── BLACKY GAME ──────────────────────
def deal_hands():
    return [[1,2,3,4],[1,2,3,4],[1,2,3,4],[1,2,3,4]]

# ── MIRO ─────────────────────────────
def miro_start_board():
    board = [None]*9
    board[0]=board[1]=board[2]='p1'
    board[6]=board[7]=board[8]='p2'
    return board

MIRO_WIN_LINES = [
    [0,1,2],[3,4,5],[6,7,8],
    [0,3,6],[1,4,7],[2,5,8],
    [0,4,8],[2,4,6],
]
MIRO_START_P1 = [0,1,2]
MIRO_START_P2 = [6,7,8]

def check_miro_win(board, player):
    for line in MIRO_WIN_LINES:
        if all(board[i]==player for i in line):
            start = MIRO_START_P1 if player=='p1' else MIRO_START_P2
            if set(line) != set(start):
                return line
    return None

MIRO_ADJ = {
    0:[1,3], 1:[0,2,4], 2:[1,5],
    3:[0,4,6], 4:[1,3,5,7], 5:[2,4,8],
    6:[3,7], 7:[6,8,4], 8:[5,7],
}

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

async def handler(ws):
    code = None
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except:
                continue
            t = msg.get("type")

            # ══════════════════════════════
            #  BLACKY GAME
            # ══════════════════════════════

            if t == "create":
                name = msg.get("name","J1")[:12]
                code = new_code()
                salons[code] = {
                    'game': 'blacky',
                    'players': {},
                    'names': [None]*4,
                    'hands': [[],[],[],[]],
                    'turn': 0,
                    'score': [0,0],
                    'started': False
                }
                salon = salons[code]
                salon['players'][ws] = {'index':0,'name':name}
                salon['names'][0] = name
                await send_to(ws, {"type":"created","code":code,"your_index":0})
                await blacky_lobby(code)

            elif t == "join":
                name = msg.get("name","J?")[:12]
                jcode = msg.get("code","").strip()
                if jcode not in salons or salons[jcode]['game']!='blacky':
                    await send_to(ws,{"type":"error","msg":"Code invalide !"}); continue
                salon = salons[jcode]
                if salon['started']:
                    await send_to(ws,{"type":"error","msg":"Partie déjà commencée !"}); continue
                idx = next((i for i in range(4) if salon['names'][i] is None),None)
                if idx is None:
                    await send_to(ws,{"type":"error","msg":"Salon plein !"}); continue
                code = jcode
                salon['players'][ws] = {'index':idx,'name':name}
                salon['names'][idx] = name
                await send_to(ws,{"type":"joined","your_index":idx})
                await blacky_lobby(code)

            elif t == "start":
                if code not in salons: continue
                salon = salons[code]
                if salon['players'][ws]['index']!=0: continue
                if sum(1 for n in salon['names'] if n)<4:
                    await send_to(ws,{"type":"error","msg":"Pas assez de joueurs"}); continue
                salon['hands'] = deal_hands()
                salon['turn'] = 0
                salon['score'] = [0,0]
                salon['started'] = True
                for ws2,info in list(salon['players'].items()):
                    i = info['index']
                    await send_to(ws2,{"type":"game_start","players":salon['names'],"hand":salon['hands'][i],"your_index":i,"current_turn":0,"score":salon['score']})

            elif t == "pass_card":
                if code not in salons: continue
                salon = salons[code]
                if not salon['started']: continue
                from_idx = salon['players'][ws]['index']
                if from_idx!=salon['turn']:
                    await send_to(ws,{"type":"error","msg":"Pas votre tour !"}); continue
                card = msg.get("card")
                if card not in salon['hands'][from_idx]:
                    await send_to(ws,{"type":"error","msg":"Carte invalide"}); continue
                to_idx = (from_idx+1)%4
                salon['hands'][from_idx].remove(card)
                salon['hands'][to_idx].append(card)
                next_turn = (salon['turn']+1)%4
                salon['turn'] = next_turn
                for ws2,info in list(salon['players'].items()):
                    i = info['index']
                    await send_to(ws2,{"type":"card_passed","from_index":from_idx,"to_index":to_idx,"card":card,"next_turn":next_turn,"hand":salon['hands'][i],"from_name":salon['names'][from_idx],"to_name":salon['names'][to_idx]})
                for i in range(4):
                    h = salon['hands'][i]
                    if len(h)==4 and len(set(h))==1:
                        team = 0 if i in (0,2) else 1
                        salon['score'][team]+=1
                        for ws2 in list(salon['players']):
                            await send_to(ws2,{"type":"win","winner_index":i,"winner_name":salon['names'][i],"team":team,"score":salon['score']})
                        salon['started']=False
                        salon['hands']=[[],[],[],[]]
                        break

            elif t == "rematch":
                if code not in salons: continue
                salon = salons[code]
                if salon['players'][ws]['index']!=0: continue
                salon['hands']=deal_hands()
                salon['turn']=0
                salon['started']=True
                for ws2,info in list(salon['players'].items()):
                    i=info['index']
                    await send_to(ws2,{"type":"game_start","players":salon['names'],"hand":salon['hands'][i],"your_index":i,"current_turn":0,"score":salon['score']})

            # ══════════════════════════════
            #  MIRO
            # ══════════════════════════════

            elif t == "miro_create":
                name = msg.get("name","J1")[:12]
                color = msg.get("color","red")
                code = new_code()
                salons[code] = {
                    'game': 'miro',
                    'players': {},
                    'pinfo': [None,None],
                    'board': None,
                    'turn': 'p1',
                    'score': [0,0],
                    'started': False,
                    'taken_colors': [color]
                }
                salon = salons[code]
                salon['players'][ws] = {'index':0,'name':name,'color':color,'player':'p1'}
                salon['pinfo'][0] = {'name':name,'color':color,'player':'p1'}
                await send_to(ws,{"type":"miro_created","code":code,"your_index":0})
                await miro_lobby(code)

            elif t == "miro_join":
                name = msg.get("name","J?")[:12]
                color = msg.get("color","blue")
                jcode = msg.get("code","").strip()
                if jcode not in salons or salons[jcode]['game']!='miro':
                    await send_to(ws,{"type":"error","msg":"Code invalide !"}); continue
                salon = salons[jcode]
                if salon['started']:
                    await send_to(ws,{"type":"error","msg":"Partie déjà commencée !"}); continue
                if salon['pinfo'][1] is not None:
                    await send_to(ws,{"type":"error","msg":"Salon plein !"}); continue
                if color in salon['taken_colors']:
                    await send_to(ws,{"type":"error","msg":"Couleur déjà prise !"}); continue
                code = jcode
                salon['taken_colors'].append(color)
                salon['players'][ws] = {'index':1,'name':name,'color':color,'player':'p2'}
                salon['pinfo'][1] = {'name':name,'color':color,'player':'p2'}
                await send_to(ws,{"type":"miro_joined","your_index":1})
                await miro_lobby(code)

            elif t == "miro_start":
                if code not in salons: continue
                salon = salons[code]
                if salon['players'][ws]['index']!=0: continue
                if salon['pinfo'][1] is None:
                    await send_to(ws,{"type":"error","msg":"En attente du 2ème joueur !"}); continue
                salon['board'] = miro_start_board()
                salon['turn'] = 'p1'
                salon['started'] = True
                for ws2,info in list(salon['players'].items()):
                    await send_to(ws2,{"type":"miro_start","board":salon['board'],"turn":salon['turn'],"players":salon['pinfo'],"score":salon['score']})

            elif t == "miro_move":
                if code not in salons: continue
                salon = salons[code]
                if not salon['started']: continue
                player = salon['players'][ws]['player']
                if player!=salon['turn']:
                    await send_to(ws,{"type":"error","msg":"Pas votre tour !"}); continue
                frm = msg.get("from")
                to  = msg.get("to")
                board = salon['board']
                if board[frm]!=player or board[to] is not None or to not in MIRO_ADJ[frm]:
                    await send_to(ws,{"type":"error","msg":"Mouvement invalide !"}); continue
                board[frm]=None
                board[to]=player
                win_line = check_miro_win(board,player)
                next_turn = 'p2' if player=='p1' else 'p1'
                salon['turn'] = next_turn
                if win_line:
                    pinfo = salon['players'][ws]
                    salon['score'][pinfo['index']]+=1
                    salon['started']=False
                    for ws2 in list(salon['players']):
                        await send_to(ws2,{"type":"miro_win","winner":player,"winner_name":pinfo['name'],"winner_color":pinfo['color'],"win_line":win_line,"score":salon['score'],"board":board})
                else:
                    for ws2 in list(salon['players']):
                        await send_to(ws2,{"type":"miro_move","board":board,"turn":next_turn})

            elif t == "miro_rematch":
                if code not in salons: continue
                salon = salons[code]
                if salon['players'][ws]['index']!=0: continue
                salon['board']=miro_start_board()
                salon['turn']='p1'
                salon['started']=True
                for ws2,info in list(salon['players'].items()):
                    await send_to(ws2,{"type":"miro_start","board":salon['board'],"turn":salon['turn'],"players":salon['pinfo'],"score":salon['score']})

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if code and code in salons:
            salon = salons[code]
            if ws in salon['players']:
                info = salon['players'][ws]
                if salon['game']=='blacky':
                    salon['names'][info['index']]=None
                else:
                    salon['pinfo'][info['index']]=None
                del salon['players'][ws]
                salon['started']=False
            if not salon['players']:
                del salons[code]

async def blacky_lobby(code):
    if code not in salons: return
    salon = salons[code]
    for ws2,info in list(salon['players'].items()):
        await send_to(ws2,{"type":"lobby_state","players":salon['names'],"your_index":info['index'],"code":code})

async def miro_lobby(code):
    if code not in salons: return
    salon = salons[code]
    for ws2,info in list(salon['players'].items()):
        await send_to(ws2,{"type":"miro_lobby","players":[p for p in salon['pinfo'] if p],"code":code,"takenColors":salon['taken_colors']})

async def main():
    print(f"DIGAMES serveur port {PORT}")
    async with websockets.serve(handler,"0.0.0.0",PORT):
        await asyncio.Future()

asyncio.run(main())
