import streamlit as st
#st.set_page_config(layout="wide")   
## Title
st.title('UAM 기상 정보 가시화')
## Header/Subheader
#st.header('This is header')
#st.subheader('This is subheader')
## Text
st.text("가시화 테스트")

import tqdm
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, writers
from matplotlib.collections import LineCollection
import matplotlib.ticker as ticker
from netCDF4 import Dataset
import contextily as cx
import mpld3
from PIL import Image
import base64

## Date Input
import datetime
today = st.date_input("날짜를 선택하세요.", datetime.date(2021, 10, 15))
the_time = st.time_input("시간을 입력하세요.", datetime.time(6,30))

import os
path = os.path.dirname(__file__)

class Streamlines(object):
    """
    Copyright (c) 2011 Raymond Speth.
    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:
    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.
    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.
    See: http://web.mit.edu/speth/Public/streamlines.py
    """

    def __init__(self, X, Y, U, V, res=0.125,
                 spacing=2, maxLen=2500, detectLoops=False):
        """
        Compute a set of streamlines covering the given velocity field.
        X and Y - 1D or 2D (e.g. generated by np.meshgrid) arrays of the
                  grid points. The mesh spacing is assumed to be uniform
                  in each dimension.
        U and V - 2D arrays of the velocity field.
        res - Sets the distance between successive points in each
              streamline (same units as X and Y)
        spacing - Sets the minimum density of streamlines, in grid points.
        maxLen - The maximum length of an individual streamline segment.
        detectLoops - Determines whether an attempt is made to stop extending
                      a given streamline before reaching maxLen points if
                      it forms a closed loop or reaches a velocity node.
        Plots are generated with the 'plot' or 'plotArrows' methods.
        """

        self.spacing = spacing
        self.detectLoops = detectLoops
        self.maxLen = maxLen
        self.res = res

        xa = np.asanyarray(X)
        ya = np.asanyarray(Y)
        self.x = xa if xa.ndim == 1 else xa[0]
        self.y = ya if ya.ndim == 1 else ya[:,0]
        self.u = U
        self.v = V
        self.dx = (self.x[-1]-self.x[0])/(self.x.size-1) # assume a regular grid
        self.dy = (self.y[-1]-self.y[0])/(self.y.size-1) # assume a regular grid
        self.dr = self.res * np.sqrt(self.dx * self.dy)

        # marker for which regions have contours
        self.used = np.zeros(self.u.shape, dtype=bool)
        self.used[0] = True
        self.used[-1] = True
        self.used[:,0] = True
        self.used[:,-1] = True

        # Don't try to compute streamlines in regions where there is no velocity data
        for i in range(self.x.size):
            for j in range(self.y.size):
                if self.u[j,i] == 0.0 and self.v[j,i] == 0.0:
                    self.used[j,i] = True

        # Make the streamlines
        self.streamlines = []
        while not self.used.all():
            nz = np.transpose(np.logical_not(self.used).nonzero())
            # Make a streamline starting at the first unrepresented grid point
            self.streamlines.append(self._makeStreamline(self.x[nz[0][1]],
                                                         self.y[nz[0][0]]))


    def _interp(self, x, y):
        """ Compute the velocity at point (x,y) """
        i = (x-self.x[0])/self.dx
        ai = i % 1

        j = (y-self.y[0])/self.dy
        aj = j % 1

        i, j = int(i), int(j)

        # Bilinear interpolation
        u = (self.u[j,i]*(1-ai)*(1-aj) +
             self.u[j,i+1]*ai*(1-aj) +
             self.u[j+1,i]*(1-ai)*aj +
             self.u[j+1,i+1]*ai*aj)

        v = (self.v[j,i]*(1-ai)*(1-aj) +
             self.v[j,i+1]*ai*(1-aj) +
             self.v[j+1,i]*(1-ai)*aj +
             self.v[j+1,i+1]*ai*aj)

        self.used[j:j+self.spacing,i:i+self.spacing] = True

        return u,v

    def _makeStreamline(self, x0, y0):
        """
        Compute a streamline extending in both directions from the given point.
        """

        sx, sy = self._makeHalfStreamline(x0, y0, 1) # forwards
        rx, ry = self._makeHalfStreamline(x0, y0, -1) # backwards

        rx.reverse()
        ry.reverse()

        return rx+[x0]+sx, ry+[y0]+sy

    def _makeHalfStreamline(self, x0, y0, sign):
        """
        Compute a streamline extending in one direction from the given point.
        """

        xmin = self.x[0]
        xmax = self.x[-1]
        ymin = self.y[0]
        ymax = self.y[-1]

        sx = []
        sy = []

        x = x0
        y = y0
        i = 0
        while xmin < x < xmax and ymin < y < ymax:
            u, v = self._interp(x, y)
            theta = np.arctan2(v,u)

            x += sign * self.dr * np.cos(theta)
            y += sign * self.dr * np.sin(theta)
            sx.append(x)
            sy.append(y)

            i += 1

            if self.detectLoops and i % 10 == 0 and self._detectLoop(sx, sy):
                break

            if i > self.maxLen / 2:
                break

        return sx, sy

    def _detectLoop(self, xVals, yVals):
        """ Detect closed loops and nodes in a streamline. """
        x = xVals[-1]
        y = yVals[-1]
        D = np.array([np.hypot(x-xj, y-yj)
                      for xj,yj in zip(xVals[:-1],yVals[:-1])])
        return (D < 0.9 * self.dr).any()


def plotvar(ncdata,fig,ax,varname):
    Y= ncdata.variables['lat']
    X= ncdata.variables['lon']
    temp = ncdata.variables[varname][hgt_idx,:,:]
    unit = ncdata.variables[varname].units
    if (varname=="tke"):
        plt.contourf(X[0,:],Y[:,0],temp,alpha=0.7,locator = ticker.MaxNLocator(prune = 'lower'))
        c = plt.colorbar(shrink=0.7)
        c.set_label(unit)
    else:
        plt.contourf(X[0,:],Y[:,0],temp,alpha=0.7)
        c = plt.colorbar(shrink=0.7)
        c.set_label(unit)

def plotvar2D(ncdata,fig,ax,varname):
    Y= ncdata.variables['lat']
    X= ncdata.variables['lon']
    temp = ncdata.variables[varname][:,:]
    unit = ncdata.variables[varname].units
    if (varname=="tke"):
        plt.contourf(X[0,:],Y[:,0],temp,alpha=0.7,locator = ticker.MaxNLocator(prune = 'lower'))
        c = plt.colorbar(shrink=0.7)
        c.set_label(unit)
    else:
        plt.contourf(X[0,:],Y[:,0],temp,alpha=0.7)
        c = plt.colorbar(shrink=0.7)
        c.set_label(unit)
            
def plotstreamline(ncdata,fig,ax):
    Y = ncdata.variables['lat']
    X = ncdata.variables['lon']
    U = ncdata.variables['u'][hgt_idx,:,:]
    V = ncdata.variables['v'][hgt_idx,:,:]
    #U, V = -1 - X**2 + Y, 1 + X - X*Y**2
    speed = np.sqrt(U*U + V*V)

    lengths = []
    colors = []
    lines = []

    s = Streamlines(X, Y, U, V)
    for streamline in s.streamlines:
        x, y = streamline
        points = np.array([x, y]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)
        n = len(segments)

        D = np.sqrt(((points[1:] - points[:-1])**2).sum(axis=-1))
        L = D.cumsum().reshape(n,1) + np.random.uniform(0,1)
        C = np.zeros((n,3))
        C[:] = (L*1.5) % 1

        #linewidths = np.zeros(n)
        #linewidths[:] = 1.5 - ((L.reshape(n)*1.5) % 1)

        # line = LineCollection(segments, color=colors, linewidth=linewidths)
        line = LineCollection(segments, color=C, linewidth=0.5)
        lengths.append(L)
        colors.append(C)
        lines.append(line)

        ax.add_collection(line)

    ax.set_xlim(X[0,0],X[-1,-1])
    #ax.set_xticks([])
    ax.set_ylim(Y[0,0],Y[-1,-1])
    #ax.set_yticks([])
    plt.tight_layout()

    cx.add_basemap(ax, crs=4004,source=cx.providers.CartoDB.Positron) #crs='WGS84',
        
    def update(frame_no):
        for i in range(len(lines)):
            lengths[i] += 0.01
            colors[i][:] = (lengths[i]*1.5) % 1
            lines[i].set_color(colors[i])
        pbar.update()
        
        
    n = 60
    # animation = FuncAnimation(fig, update, interval=10)
    animation = FuncAnimation(fig, update, frames=n, interval=20)
    pbar = tqdm.tqdm(total=n)
    # animation.save('wind.mp4', writer='ffmpeg', fps=60)
    animation.save('wind.gif', writer='imagemagick', fps=60)
    pbar.close()
    #plt.show()

    file_ = open("./wind.gif", "rb")
    contents = file_.read()
    data_url = base64.b64encode(contents).decode("utf-8")
    file_.close()
    cont.markdown(f'<img src="data:image/gif;base64,{data_url}" alt="cat gif" style="display: block; margin: 0 auto;" width="700">',unsafe_allow_html=True)
#parameter 0 = stream line
#@st.cache(suppress_st_warning=True)
def load_data(date, time, isstreamline, parameter):
    ncf0 = Dataset(path+'/data/uamwx_'+date+'_'+time+'.nc', mode = 'r', format = 'NETCDF4_CLASSIC')
    fig = plt.figure(figsize=(10,4.5))
    ax = plt.subplot(1, 1, 1, aspect=1)
    
    if (parameter=="기온"):
        plotvar(ncf0,fig,ax,"temp")
    elif (parameter=="습도"):
        plotvar(ncf0,fig,ax,"rh")
    elif (parameter=="시정"):
        plotvar(ncf0,fig,ax,"vis")
    elif (parameter=="운고"):
        plotvar2D(ncf0,fig,ax,"lcl")
    elif (parameter=="tke"):
        plotvar(ncf0,fig,ax,"tke")
    elif (parameter=="edr"):
        plotvar(ncf0,fig,ax,"edr")
    elif (parameter=="강수"):
        plotvar2D(ncf0,fig,ax,"pcp")
    elif (parameter=="W"):
        plotvar(ncf0,fig,ax,"w")
    else:
        st.warning("오류입니당.")
     
    if (isstreamline=="Active"):
        plotstreamline(ncf0,fig,ax)
    else:
        cx.add_basemap(ax, crs=4004,source=cx.providers.CartoDB.Positron) #crs='WGS84',
        plt.tight_layout()
        plt.savefig('savefig_default.png')
        file_ = open("./savefig_default.png", "rb")
        contents = file_.read()
        data_url = base64.b64encode(contents).decode("utf-8")
        file_.close()
        cont.markdown(f'<img src="data:image/gif;base64,{data_url}" alt="cat gif" style="display: block; margin: 0 auto;" width="700">',unsafe_allow_html=True)

date_info =str(today)[0:4]+str(today)[5:7]+str(today)[8:10]
time_info = str(the_time)[0:2]+str(the_time)[3:5]+str(the_time)[6:8]

 
## Radio button
status = st.radio("Streamline 활성화 여부", ("Active", "Inactive"))
height = st.slider("고도를 선택하세요",0.0,3116.798,164.042,164.042)
hgt_idx = height//164.042
cols= st.columns([1,1,1,1,1,1,1,1,1,1])
cont = st.container()
with cols[0]:
    if st.button("기온"):
        load_data(date_info,time_info, status, "기온")
with cols[1]:
    if st.button("풍속"):
        st.warning("준비되지않음")
with cols[2]:
    if st.button("풍향"):
        st.warning("준비되지않음")
with cols[3]:
    if st.button("습도"):
        load_data(date_info,time_info, status, "습도")
with cols[4]:
   if st.button("시정"):
        load_data(date_info,time_info, status, "시정")
with cols[5]:
    if st.button("운고"):
        load_data(date_info,time_info, status, "운고")
with cols[6]:
    if st.button("tke"):
        load_data(date_info,time_info, status, "tke")
with cols[7]:
    if st.button("edr"):
        load_data(date_info,time_info, status, "edr")
with cols[8]:
    if st.button("강수"):
        load_data(date_info,time_info, status, "강수")
with cols[9]:
    if st.button("W"):
        load_data(date_info,time_info, status, "W")
## Select Box
#container = st.container()


#if st.button("기온"):
#  load_data(date_info,time_info, status, "wxvalue")


  
  
