import re,sys
from ttdat2 import Dat
from win import GAMES
G='L:/SteamLibrary/steamapps/common/'+GAMES[sys.argv[1]][0]+'/'
log=open(sys.argv[2] if len(sys.argv)>2 else 'work/log.txt',encoding='latin-1').read()
Ds={}
for dat,i in re.findall(r'read (\S+) #(\d+)',log):
    D=Ds.get(dat) or Ds.setdefault(dat,Dat(G+dat)); nm=D.path_of(int(i)) or '?'
    if re.search(sys.argv[3] if len(sys.argv)>3 else r'\.(csv|ft2|fnt)$|text|english|font',nm,re.I): print(dat,i,nm)
