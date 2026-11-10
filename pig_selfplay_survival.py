# Tự chơi giả lập đến khi THUA (heo chạm vạch trên) hoặc hết lượt: đếm số lượt sống và số L10. python pig_selfplay_survival.py TÊN '{"w_safe":0}' 1,2,3,4 kq.jsonl
# Ván giả lập thường thua ~200-260 lượt (khớp 2 ván thật thua ở 244 và 261). Cần >= 8 ván/bên mới đủ tin; bản thử mới có 4 ván/bên.
import sys, json, random, time
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import pig_bot as pb
W,H=692,787
WORLD=pb.SimParams(gravity=1.19,damping=0.30,friction=0.59,elasticity=0.005,rad_scale=1.035)
BOT=pb.SimParams()
LV=[1]*31+[2]*28+[3]*28+[4]*14
def play(seed,ep_kw,turns=300,think=0.3,n_x=15,topk=4):
    rnd=random.Random(seed); ep=pb.EvalParams(**ep_kw)
    balls=[]; score=0.0; dead=False; t0=time.time(); l10=0; first10=None
    for t in range(turns):
        lv=rnd.choice(LV); r=pb.r_for(lv,W)
        x,info=pb.choose_drop(balls,(lv,r),W,H,BOT,ep,think_s=think,n_x=n_x,topk=topk)
        xa=min(max(r,x+rnd.gauss(0,3.0)),W-r)
        balls,g=pb.simulate(balls,W,H,(lv,xa,r,-pb.HELD_TOP*W+r),WORLD)
        balls=[tuple(b) for b in balls]; score+=g
        l10=max(l10,sum(1 for b in balls if b[0]>=10))
        if l10 and first10 is None: first10=t+1
        if min((y-rr for _,_,y,rr in balls),default=H)<0: dead=True; break    # thua thật: heo chạm vạch trên
    mb=max(balls,key=lambda b:(b[0],b[3])) if balls else None
    return dict(seed=seed,turns=t+1,dead=dead,l10=l10,first10=first10,maxlv=mb[0] if mb else 0,score=score,sec=round(time.time()-t0))
if __name__=="__main__":
    name=sys.argv[1]; kw=json.loads(sys.argv[2]); seeds=[int(a) for a in sys.argv[3].split(",")]; out=sys.argv[4]
    for sd in seeds:
        r=play(sd,kw); r["variant"]=name; open(out,"a").write(json.dumps(r)+"\n")
