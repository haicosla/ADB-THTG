# Tự chơi giả lập (không cần LDPlayer) để A/B EvalParams: python pig_selfplay.py TÊN '{"w_corner":30}' 1,2,3 kết_quả.jsonl
# WORLD = tham số vật lý "thật" (hiệu chỉnh từ phiên chơi), BOT = mô hình của bot -> cố ý lệch nhau để không tự khen mình. Điểm dao động mạnh giữa các ván (±~220 sai số chuẩn/8 ván) nên cần >= 8 ván/bên.
import sys, json, random, time, math
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import pig_bot as pb
W,H=692,787
WORLD=pb.SimParams(gravity=1.19,damping=0.30,friction=0.59,elasticity=0.005,rad_scale=1.035)   # tham số thật hiệu chỉnh từ phiên chơi
BOT=pb.SimParams()
LV=[1]*31+[2]*28+[3]*28+[4]*14
def play(seed,ep_kw,turns=130,think=0.5,n_x=15,topk=4,verbose=False):
    rnd=random.Random(seed)
    ep=pb.EvalParams(**ep_kw)
    balls=[]; score=0.0; dead=False; t0=time.time()
    for t in range(turns):
        lv=rnd.choice(LV); r=pb.r_for(lv,W)
        x,info=pb.choose_drop(balls,(lv,r),W,H,BOT,ep,think_s=think,n_x=n_x,topk=topk)
        xa=min(max(r,x+rnd.gauss(0,3.0)),W-r)                      # sai số bấm
        balls,g=pb.simulate(balls,W,H,(lv,xa,r,-pb.HELD_TOP*W+r),WORLD)
        balls=[tuple(b) for b in balls]
        score+=g
        top=min((y-rr for _,_,y,rr in balls),default=H)
        if top<0.10*H: dead=True; break
    mb=max(balls,key=lambda b:(b[0],b[3])) if balls else None
    small=sum(1 for b in balls if b[0]<=2)
    gap=min(mb[1]-mb[3],W-mb[1]-mb[3])/W if mb else 1
    return dict(seed=seed,score=score,turns=t+1,dead=dead,n=len(balls),maxlv=mb[0] if mb else 0,
                small=small,corner_gap=round(gap,3),top=round(top/H,3),sec=round(time.time()-t0))
if __name__=="__main__":
    name=sys.argv[1]; kw=json.loads(sys.argv[2]); seeds=[int(a) for a in sys.argv[3].split(",")]
    out=sys.argv[4]
    for sd in seeds:
        r=play(sd,kw); r["variant"]=name
        open(out,"a").write(json.dumps(r)+"\n"); print(r,flush=True)
