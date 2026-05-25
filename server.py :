import asyncio
import websockets
import json
import os
import random

PORT = int(os.environ.get("PORT", 10000))

salons = {}

def deal_hands():
    return [[1,2,3,4],[1,2,3,4],[1,2,3,4],[1,2,3,4]]

def miro_board():
    b = [None]*9
    b[0]=b[1]=b[2]='p1'
    b[6]=b[7]=b[8]='p2'
    return b

MWIN = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]]
MADJ = {0:[1,3],1:[0,2,4],2:[1,5],3:[0,4,6],4:[1,3,5,7],5:[2,4,8],6:[3,7],7:[6,8,4],8:[5,7]}

def check_win(board, player):
    start = [0,1,2] if player=='p1' else [6,7,8]
    for line in MWIN:
        if all(board[i]==player for i in line):
            if set(line) != set(start):
                return line
    return None

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

            # ══ BLACKY ══

            if t == "create":
                name = msg.get("name","J1")[:12]
                code = new_code()
                salons[code] = {
                    'game':'blacky','players':{},'names':[None]*4,
                    'hands':[[],[],[],[]],'turn':0,'score':[0,0],'started':False
                }
                salons[code]['players'][ws] = {'index':0,'name':name}
                salons[code]['names'][0] = name
                await send_to(ws,{"type":"created","code":code,"your_index":0})
                await blacky_lobby(code)

            elif t == "join":
                name = msg.get("name","J")[:12]
                jcode = msg.get("code","").strip()
                if jcode not in salons or salons[jcode]['game']!='blacky':
                    await send_to(ws,{"type":"error","msg":"Code invalide !"}); continue
                s = salons[jcode]
                if s['started']:
                    await send_to(ws,{"type":"error","msg":"Partie déjà commencée !"}); continue
                idx = next((i for i in range(4) if s['names'][i] is None),None)
                if idx is None:
                    await send_to(ws,{"type":"error","msg":"Salon plein !"}); continue
                code = jcode
                s['players'][ws] = {'index':idx,'name':name}
                s['names'][idx] = name
                await send_to(ws,{"type":"joined","your_index":idx})
                await blacky_lobby(code)

            elif t == "start":
                if code not in salons: continue
                s = salons[code]
                if s['players'][ws]['index']!=0: continue
                if sum(1 for n in s['names'] if n)<4:
                    await send_to(ws,{"type":"error","msg":"Pas assez de joueurs"}); continue
                s['hands']=deal_hands(); s['turn']=0; s['score']=[0,0]; s['started']=True
                for ws2,info in list(s['players'].items()):
                    i=info['index']
                    await send_to(ws2,{"type":"game_start","players":s['names'],"hand":s['hands'][i],"your_index":i,"current_turn":0,"score":s['score']})

            elif t == "pass_card":
                if code not in salons: continue
                s = salons[code]
                if not s['started']: continue
                fi = s['players'][ws]['index']
                if fi!=s['turn']:
                    await send_to(ws,{"type":"error","msg":"Pas votre tour !"}); continue
                card=msg.get("card")
                if card not in s['hands'][fi]:
                    await send_to(ws,{"type":"error","msg":"Carte invalide"}); continue
                ti=(fi+1)%4
                s['hands'][fi].remove(card); s['hands'][ti].append(card)
                nt=(s['turn']+1)%4; s['turn']=nt
                for ws2,info in list(s['players'].items()):
                    i=info['index']
                    await send_to(ws2,{"type":"card_passed","from_index":fi,"to_index":ti,"card":card,"next_turn":nt,"hand":s['hands'][i],"from_name":s['names'][fi],"to_name":s['names'][ti]})
                for i in range(4):
                    h=s['hands'][i]
                    if len(h)==4 and len(set(h))==1:
                        team=0 if i in(0,2) else 1
                        s['score'][team]+=1
                        for ws2 in list(s['players']):
                            await send_to(ws2,{"type":"win","winner_index":i,"winner_name":s['names'][i],"team":team,"score":s['score']})
                        s['started']=False; s['hands']=[[],[],[],[]]; break

            elif t == "rematch":
                if code not in salons: continue
                s = salons[code]
                if s['players'][ws]['index']!=0: continue
                s['hands']=deal_hands(); s['turn']=0; s['started']=True
                for ws2,info in list(s['players'].items()):
                    i=info['index']
                    await send_to(ws2,{"type":"game_start","players":s['names'],"hand":s['hands'][i],"your_index":i,"current_turn":0,"score":s['score']})

            # ══ MIRO ══

            elif t == "miro_create":
                name=msg.get("name","J1")[:12]; color=msg.get("color","red")
                code=new_code()
                salons[code]={'game':'miro','players':{},'pinfo':[None,None],'board':None,'turn':'p1','score':[0,0],'started':False,'taken':[color]}
                salons[code]['players'][ws]={'index':0,'name':name,'color':color,'player':'p1'}
                salons[code]['pinfo'][0]={'name':name,'color':color,'player':'p1'}
                await send_to(ws,{"type":"miro_created","code":code,"your_index":0})
                await miro_lobby(code)

            elif t == "miro_join":
                name=msg.get("name","J")[:12]; color=msg.get("color","blue")
                jcode=msg.get("code","").strip()
                if jcode not in salons or salons[jcode]['game']!='miro':
                    await send_to(ws,{"type":"error","msg":"Code invalide !"}); continue
                s=salons[jcode]
                if s['started']:
                    await send_to(ws,{"type":"error","msg":"Partie commencée !"}); continue
                if s['pinfo'][1] is not None:
                    await send_to(ws,{"type":"error","msg":"Salon plein !"}); continue
                if color in s['taken']:
                    await send_to(ws,{"type":"error","msg":"Couleur déjà prise !"}); continue
                code=jcode; s['taken'].append(color)
                s['players'][ws]={'index':1,'name':name,'color':color,'player':'p2'}
                s['pinfo'][1]={'name':name,'color':color,'player':'p2'}
                await send_to(ws,{"type":"miro_joined","your_index":1})
                await miro_lobby(code)

            elif t == "miro_start":
                if code not in salons: continue
                s=salons[code]
                if s['players'][ws]['index']!=0: continue
                if s['pinfo'][1] is None:
                    await send_to(ws,{"type":"error","msg":"En attente du 2ème joueur !"}); continue
                s['board']=miro_board(); s['turn']='p1'; s['started']=True
                for ws2 in list(s['players']):
                    await send_to(ws2,{"type":"miro_start","board":s['board'],"turn":s['turn'],"players":s['pinfo'],"score":s['score']})

            elif t == "miro_move":
                if code not in salons: continue
                s=salons[code]
                if not s['started']: continue
                player=s['players'][ws]['player']
                if player!=s['turn']:
                    await send_to(ws,{"type":"error","msg":"Pas votre tour !"}); continue
                frm=msg.get("from"); to=msg.get("to")
                board=s['board']
                if board[frm]!=player or board[to] is not None or to not in MADJ[frm]:
                    await send_to(ws,{"type":"error","msg":"Mouvement invalide !"}); continue
                board[frm]=None; board[to]=player
                win_line=check_win(board,player)
                nt='p2' if player=='p1' else 'p1'
                s['turn']=nt
                if win_line:
                    info=s['players'][ws]
                    s['score'][info['index']]+=1; s['started']=False
                    for ws2 in list(s['players']):
                        await send_to(ws2,{"type":"miro_win","winner":player,"winner_name":info['name'],"winner_color":info['color'],"win_line":win_line,"score":s['score'],"board":board})
                else:
                    for ws2 in list(s['players']):
                        await send_to(ws2,{"type":"miro_move","board":board,"turn":nt})

            elif t == "miro_rematch":
                if code not in salons: continue
                s=salons[code]
                if s['players'][ws]['index']!=0: continue
                s['board']=miro_board(); s['turn']='p1'; s['started']=True
                for ws2 in list(s['players']):
                    await send_to(ws2,{"type":"miro_start","board":s['board'],"turn":s['turn'],"players":s['pinfo'],"score":s['score']})

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if code and code in salons:
            s=salons[code]
            if ws in s['players']:
                info=s['players'][ws]
                if s['game']=='blacky': s['names'][info['index']]=None
                else: s['pinfo'][info['index']]=None
                del s['players'][ws]; s['started']=False
            if not s['players']:
                del salons[code]

async def blacky_lobby(code):
    if code not in salons: return
    s=salons[code]
    for ws2,info in list(s['players'].items()):
        await send_to(ws2,{"type":"lobby_state","players":s['names'],"your_index":info['index'],"code":code})

async def miro_lobby(code):
    if code not in salons: return
    s=salons[code]
    for ws2,info in list(s['players'].items()):
        await send_to(ws2,{"type":"miro_lobby","players":[p for p in s['pinfo'] if p],"code":code,"takenColors":s['taken']})

async def main():
    print(f"DIGAMES port {PORT}")
    async with websockets.serve(handler,"0.0.0.0",PORT):
        await asyncio.Future()

asyncio.run(main())
