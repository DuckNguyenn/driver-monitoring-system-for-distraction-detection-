from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Ellipse, FancyBboxPatch
from matplotlib.text import Text
import numpy as np

OUT=Path('report_assets/humanized'); OUT.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none'})
INK='#263b4a'; BLUE='#eaf2f8'; GREEN='#e5f2ee'; ORANGE='#fff0da'
def canvas(w=11,h=6):
 f,a=plt.subplots(figsize=(w,h));a.set(xlim=(0,11),ylim=(0,6));a.axis('off');return f,a
def box(a,x,y,w,h,t,fill=BLUE,fs=11):
 a.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.04',facecolor=fill,edgecolor=INK,lw=1.2))
 a.text(x+w/2,y+h/2,t,ha='center',va='center',fontsize=fs,color=INK)
def arrow(a,x,y,X,Y,label=''):
 a.annotate('',(X,Y),(x,y),arrowprops={'arrowstyle':'-|>','color':INK,'lw':1.3})
 if label:a.text((x+X)/2,(y+Y)/2+.1,label,ha='center',fontsize=9,color=INK)
def readable(f):
 for t in f.findobj(Text):
  size=t.get_fontsize();t.set_fontsize(size*1.15 if size>=15 else max(13.5,size*1.35))

def save(f,name):
 readable(f)
 f.tight_layout(pad=.5);f.savefig(OUT/(name+'.png'),dpi=200,facecolor='white');f.savefig(OUT/(name+'.svg'));plt.close(f)

f,a=canvas()
a.text(.3,5.65,'Từ khung hình đến vùng ảnh phân loại',fontsize=15,weight='bold',color=INK)
a.add_patch(Rectangle((.4,1.1),4.1,3.7,fc='#f7f8fa',ec=INK))
a.add_patch(Ellipse((2.45,3),2,2.9,fc='#edf0f3',ec='#8a9aa7'))
a.add_patch(Rectangle((1.45,1.55),2,2.85,fill=False,ec=INK,lw=1.5))
a.add_patch(Rectangle((1.25,1.27),2.4,3.42,fill=False,ec='#26836b',ls='--',lw=1.3))
for x in [2,2.9]:
 a.plot(x,3.4,'o',color=INK);a.add_patch(Rectangle((x-.36,3.13),.72,.54,fill=False,ec='#206fa2',lw=1.6))
for x,y in [(2.45,2.85),(2.08,2.35),(2.82,2.35)]:a.plot(x,y,'o',color=INK)
a.annotate('',(2,3.93),(2.9,3.93),arrowprops={'arrowstyle':'<->','color':INK});a.text(2.45,4.04,'d',ha='center')
box(a,5.7,3.65,4.7,1,'Hai ROI mắt: 0,8d × 0,6d\nCùng mô hình mắt, suy luận riêng')
box(a,5.7,1.7,4.7,1,'ROI mặt: mở rộng 10% mỗi phía\nĐầu vào mô hình ngáp',GREEN)
arrow(a,3.5,3.5,5.65,4.15);arrow(a,3.65,1.9,5.65,2.2)
a.text(.45,.45,'Năm điểm mốc: hai mắt, mũi, hai khóe miệng. ROI được lấy từ ảnh gốc.\nHình nguyên lý, không phải ảnh thực nghiệm.',fontsize=10,color=INK)
save(f,'roi_landmarks')

f,a=canvas()
a.text(.3,5.6,'NMS giữ hộp có điểm cao và bỏ hộp trùng',fontsize=15,weight='bold',color=INK)
for x,t in [(.5,'Các hộp ứng viên'),(6.7,'Sau NMS')]:
 a.text(x,4.9,t,weight='bold');a.add_patch(Rectangle((x,.9),3.8,3.7,fc='#f8fafb',ec='#ccd5dc'))
for x,y,w,h,c,t in [(1.1,1.7,1.7,2.2,'#206d53','A: 0,95'),(1.35,1.5,1.7,2.2,'#b06030','B: 0,88')]:
 a.add_patch(Rectangle((x,y),w,h,fill=False,ec=c,lw=2))
 a.text(x,y+h+.12 if t.startswith('A') else y+h-.45,t,color=c)
a.add_patch(Rectangle((3.25,1.2),.65,1,fill=False,ec='#246b9a',lw=2));a.text(3.2,2.4,'C: 0,82',fontsize=9)
a.add_patch(Rectangle((7.3,1.7),1.7,2.2,fill=False,ec='#206d53',lw=2));a.text(7.3,4.02,'Giữ A',color='#206d53')
a.add_patch(Rectangle((9.45,1.2),.65,1,fill=False,ec='#246b9a',lw=2));a.text(9.4,2.4,'Giữ C',fontsize=9)
arrow(a,4.45,2.9,6.55,2.9);a.text(5.5,3.8,'IoU(A,B) > 0,30\nB bị loại',ha='center',fontsize=10)
a.text(.5,.25,'IoU = diện tích giao / diện tích hợp. Điểm số trong hình chỉ dùng minh họa.',fontsize=10)
save(f,'nms')

f,a=canvas(11,4.5)
a.text(.3,5.5,'Bộ lọc tích chập trượt trên ảnh',fontsize=15,weight='bold',color=INK)
rng=np.arange(25).reshape(5,5)%4
for row in range(5):
 for col in range(5):
  a.add_patch(Rectangle((.5+col*.5,1.5+row*.5),.5,.5,fc=BLUE,ec='white'))
  a.text(.75+col*.5,1.75+row*.5,str(rng[row,col]),ha='center',va='center',fontsize=10)
a.add_patch(Rectangle((.5,2.5),1.5,1.5,fill=False,ec='#c77523',lw=2.5))
box(a,4,2.2,2.1,1.4,'Bộ lọc 3 × 3\nNhân từng phần tử\nrồi cộng',ORANGE,10)
for row in range(3):
 for col in range(3):a.add_patch(Rectangle((8+col*.55,2+row*.55),.55,.55,fc=GREEN,ec='white'))
a.add_patch(Rectangle((8,3.1),.55,.55,fc='#c77523',ec='white'))
arrow(a,3.2,3.1,3.9,3.1);arrow(a,6.2,3.1,7.8,3.1)
a.text(1.7,1,'Ảnh 5 × 5',ha='center');a.text(8.8,1,'Đặc trưng 3 × 3',ha='center')
a.text(.5,.3,'Ví dụ stride = 1, không padding. Một ô đầu ra được tính từ một vùng 3 × 3.',fontsize=10)
save(f,'convolution')

f,axes=plt.subplots(2,1,figsize=(10,4.9),sharex=True,gridspec_kw={'height_ratios':[2,1]})
t=np.linspace(0,5,501);p=np.piecewise(t,[t<.5,(t>=.5)&(t<2),(t>=2)&(t<3),t>=3],[.2,.82,.52,.2])
axes[0].plot(t,p,color='#246b9a',lw=2,label='Xác suất dùng cho quyết định')
for v,c in [(.7,'#c77523'),(.35,'#748b9c')]:axes[0].axhline(v,color=c,ls='--',label=f'Ngưỡng {v:.2f}')
axes[0].axvspan(.5,1.5,color='#e7d8b0',alpha=.45);axes[0].axvspan(3,3.5,color='#b8d8ca',alpha=.5)
axes[0].text(1,.38,'Chờ đủ 1 s',ha='center',fontsize=10);axes[0].text(3.25,.48,'0,5 s',ha='center',fontsize=10)
axes[0].set(ylim=(0,1),ylabel='P(yawn)',title='Một đợt ngáp chỉ được đếm một lần');axes[0].legend(loc='upper right',fontsize=8)
axes[1].step(t,(t>=1.5).astype(int),where='post',color='#206d53',lw=2);axes[1].set(ylim=(-.15,1.3),yticks=[0,1],ylabel='Số đợt',xlabel='Thời gian (giây)')
axes[1].annotate('Xác nhận tại 1,5 s',xy=(1.5,1),xytext=(.1,1.12),fontsize=9,arrowprops={'arrowstyle':'->'})
axes[1].text(3.52,.35,'Kết thúc đợt tại 3,5 s',fontsize=9)
for ax in axes:ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
f.text(.5,.01,'Chuỗi minh họa thuật toán, không phải số liệu thực nghiệm.',ha='center',fontsize=9)
readable(f)
f.tight_layout(rect=(0,.04,1,1));f.savefig(OUT/'yawn_timeline.png',dpi=200);f.savefig(OUT/'yawn_timeline.svg');plt.close(f)

f,a=canvas(11,4)
a.text(.4,5.5,'Ghép hai chu kỳ mắt thành một lần chớp hai mắt',fontsize=15,weight='bold')
for y,name,left,right in [(3.8,'Mắt 1',2,5),(2.6,'Mắt 2',2.5,5.4)]:
 a.text(.5,y+.1,name);a.plot([1.8,9.8],[y,y],color='#9aabb6');a.add_patch(Rectangle((left,y-.2),right-left,.4,fc='#3189aa'))
 a.text((left+right)/2,y+.45,'Khoảng nhắm',ha='center',fontsize=10)
a.add_patch(Rectangle((2.5,1.1),2.5,.5,fc='#419c79'));a.text(3.75,.7,'Phần chồng lấp ≥ 0,05 s',ha='center',fontsize=10)
a.text(6,3.1,'Mỗi chu kỳ dài 0,05–0,50 s\nMở ổn định trước và sau\nGhép mỗi cặp một lần',fontsize=11,linespacing=1.6,bbox={'facecolor':'white','edgecolor':'none','pad':5})
a.text(.5,.15,'Sơ đồ thời gian nguyên lý. Nháy riêng một mắt chỉ tăng bộ đếm chu kỳ của mắt đó.',fontsize=9)
save(f,'blink_timeline')

f,a=canvas()
box(a,.3,4.7,2,1,'Camera / video\nKhung hình\n+ thời gian')
box(a,3.6,4.5,3.6,1.35,'PC / Radxa\nYuNet → ROI → classifier\nMonitor theo thời gian',GREEN)
box(a,8.5,4.7,2,1,'ESP32 → còi\nUSB serial + ACK',ORANGE)
arrow(a,2.35,5.2,3.55,5.2);arrow(a,7.25,5.2,8.45,5.2)
box(a,.3,2.5,2.4,1,'Nhật ký gốc\nJSONL / CSV\nsummary JSON')
box(a,3.6,2.5,3.6,1,'Snapshot + ảnh mới nhất\nHàng đợi giới hạn')
box(a,8.1,2.5,2.4,1,'Cửa sổ PC\nHiển thị tùy chọn')
arrow(a,5.4,4.45,5.4,3.55);arrow(a,3.55,4.65,1.5,3.55);arrow(a,7.25,4.65,9.3,3.55)
box(a,.3,.4,2.4,1,'Chỉ mục SQLite\nLịch sử phiên')
box(a,3.6,.4,3.6,1,'FastAPI\nREST + WebSocket + JPEG')
box(a,8.1,.4,2.4,1,'Dashboard web\nTrình duyệt')
arrow(a,1.5,2.45,1.5,1.45);arrow(a,5.4,2.45,5.4,1.45);arrow(a,2.75,.9,3.55,.9);arrow(a,7.25,.9,8.05,.9)
a.text(5.5,.02,'API chạy ở tiến trình riêng. Còi nhận quyết định trực tiếp từ runtime.',ha='center',fontsize=9)
save(f,'system_web')

f,a=canvas()
box(a,.4,4.5,3,1,'Runtime trên PC / Radxa\nKết quả + ảnh mới nhất',GREEN)
box(a,4,4.5,2.6,1,'FastAPI\nKiểm tra mã kết nối')
box(a,7.3,4.5,3.3,1,'Trình duyệt web\nReact + TypeScript')
arrow(a,3.45,5,3.95,5);arrow(a,6.65,5,7.25,5)
for x,t,c in [(.4,'WebSocket\nSnapshot trạng thái',BLUE),(4.0,'HTTP / JPEG\nẢnh có lớp vẽ',GREEN),(7.3,'REST\nPhiên, sự kiện, CSV',ORANGE)]:
 box(a,x,2.35,3 if x!=4 else 2.6,1.1,t,c);arrow(a,5.3,4.45,x+(1.5 if x!=4 else 1.3),3.5)
box(a,.4,.25,10.2,1.1,'Ba hàng tín hiệu dùng chung cửa sổ 60 s • Giá trị thiếu giữ null\nQuá 2 s chưa có dữ liệu: làm mờ và kết nối lại\nTrình duyệt hiển thị quyết định do Monitor cung cấp',fs=10)
for x in [1.9,5.3,8.8]:arrow(a,x,2.3,x,1.4)
save(f,'web_data_flow')
print('Created',len(list(OUT.glob('*.png'))),'figures')
