#!/usr/bin/env python
# coding: utf-8

# # Gcode to ABAQUS event series
#
# Programmer: Maria Vila Pouca
#
# Log file:
# Created: 19/05/2022
#
# Description:
# - Code developed for ultimaker cura .gcode type (Marlin flavour)
# - Parses Gcode into dataframe: reads filename='filename' (without extension)
# - Get velocity, coordinates and extrusion
# - Calculate delta extrusion to locate laser onn off points
# - Add laser on off points by copying previous coordinate: adress t=on_off_time for this task
# - Calculate distance
# - Calculate dtime
# - Calculate time
# - Drop unwanted columns, reorganize into t, x, y, z, laser
# - save to .inp file
#
# #NOTES:
# Removes initial code, not necessary for ABAQUS, by searching for keyword Layer:0

filename='scaffold_new'


import pandas as pd
import numpy as np
import regex as re


def getDistanceCoords(x1,y1,z1,x2,y2,z2):
    d = (x1-x2)**2 + (y1-y2)**2+ (z1-z2)**2
    dist = d**.5
    return dist
#
def getTime(F,d):
    #F in min/s to mm/s
    Fs=F/60
    time=d/Fs
    return time

def laser(row):
    if row['dE'] <= 0:
        return 0
    else:
        return 1

def onoff(row,on_off_time):
    if row['dE'] == 100:
        return on_off_time
    elif row['dE'] == -100:
        return on_off_time

def parse_Gcode(filename):

    with open(filename, 'r') as f:
        gcode = f.read()

    df=pd.DataFrame(gcode.split('\n'), columns=['gcode'])

    #remove comments, M and S commands
    df['no_comments']=df['gcode'].replace([';.*','M\d+','S\d+'],['','',''], regex=True)

    #separate G, F, E, and coords

    df['G']=df['no_comments'].str.findall(r'G\d+')
    df['G'] = [''.join(map(str, l)) for l in df['G']]

    df['F']=df['no_comments'].str.findall(r'F\d+\.*\d*')
    df['F'] = [''.join(map(str, l)) for l in df['F']]

    df['X']=df['no_comments'].str.findall(r'X-*\d*\.*\d*')
    df['X'] = [''.join(map(str, l)) for l in df['X']]

    df['Y']=df['no_comments'].str.findall(r'Y-*\d*\.*\d*')
    df['Y'] = [''.join(map(str, l)) for l in df['Y']]

    df['Z']=df['no_comments'].str.findall(r'Z-*\d*\.*\d*')
    df['Z'] = [''.join(map(str, l)) for l in df['Z']]

    df['E']=df['no_comments'].str.findall(r'E-*\d*\.*\d*')
    df['E'] = [''.join(map(str, l)) for l in df['E']]

    #create backup dataframe
    df1=df

    #Get where it actually starts by searching for string LAYER 0
    N=df['gcode'][df['gcode'].str.contains('LAYER:0', regex=False)==True].index[0]
    df = df.iloc[N:, :]

    #replace empty rows by NaN and drop first columns
    df=df.drop(['gcode','no_comments'],axis=1)

    df=df.replace([''],[np.nan],regex=True)

    #Send to Home
    df.at[N,'X']=0
    df.at[N,'Y']=0
    df.at[N,'Z']=0

    df=df[df['G'].notna() | df['E'].notna() | df['X'].notna() | df['Y'].notna()
           | df['Z'].notna() | df['F'].notna()]

    #remove letters and convert to floats
    for col in df.columns:
        df[col]=df[col].replace(['F','X','Y','Z','E'],['','','','',''], regex=True)
        if col!='G':
            df[col]=pd.to_numeric(df[col])
            df[col]=df[col].round(4)
    df.reset_index(drop=True, inplace=True)


    return df


df=parse_Gcode(filename+'.gcode')


#drop G columns
df=df.drop('G', axis=1)

#Get whenever F value changes and replace following NaN for current F value
df['F']=df['F'].ffill(axis = 0)
df['F']=df['F'].bfill(axis = 0)


#remove lines whithout any coordinate x, y, z and E
df=df[df['E'].notna() | df['X'].notna() | df['Y'].notna()
       | df['Z'].notna()]
#Reset index coordinates
df.reset_index(drop=True, inplace=True)


#Get whenever X,Y,Z and E value changes and replace following NaN for current X,Y,Z and E value
df['X']=df['X'].ffill(axis = 0)
df['Y']=df['Y'].ffill(axis = 0)
df['Z']=df['Z'].ffill(axis = 0)

#Replace NaN by zero in E columns
df['E']=df['E'].replace([np.nan],[0],regex=True)

#Get deltaE columns
df['dE']=df['E'].diff()
df['dE']=df['dE'].replace([np.nan],[0],regex=True)


df1=df
for i in range(df.shape[0]):
    if i==0:
        dE0=df.dE[i]
    else:
        if dE0<=0 and df.dE[i]>0:
            df1.loc[i-0.5]=df.iloc[i-1,:]
            df1.at[i-0.5,'dE']=100
            df1 = df1.sort_index()
        elif dE0>0 and df.dE[i]<=0:
            df1.loc[i-0.5]=df.iloc[i-1,:]
            df1.at[i-0.5,'dE']=-100
            df1 = df1.sort_index()
    dE0=df.dE[i]
df1.reset_index(drop=True, inplace=True)


#Address laser values
df1['laser'] = df1.apply(lambda row: laser(row), axis=1)

#Address dtime due to on_off values
on_off_time=0.001
df1['Dtime']=np.nan
df1['Dtime'] = df1.apply(lambda row: onoff(row,on_off_time), axis=1)


#Calculate distance vector
df1['Distance'] = np.nan
for i in range(len(df1)):
    #get  first set of  coordinates and define distance = 0
    if i==0:
        x1=df1.X[i]
        y1=df1.Y[i]
        z1=df1.Z[i]
    else:
        x2=df1.X[i]
        y2=df1.Y[i]
        z2=df1.Z[i]
        dist=getDistanceCoords(x1,y1,z1,x2,y2,z2)
        df1.at[i,'Distance']=dist
        #update previous coordinates
        x1=x2
        y1=y2
        z1=z2

#Replace NaN by zero in Distance columns
df1['Distance']=df1['Distance'].replace([np.nan],[0],regex=True)


#Calculate Dtime vector
for i in range(len(df1)):
    if df1.Distance[i]==0.0 and np.isnan(df1.Dtime[i])==True:
        df1.at[i,'Dtime']=0
    elif df1.Distance[i]!=0:
        d4=df1.Distance[i]
        F4=df1.F[i]
        time=getTime(F4,d4)
        df1.at[i,'Dtime']=time

#remove unwanted initial procedures
N=df1[df1['Dtime']==on_off_time].Dtime.index[0]
df1=df1.iloc[N-1:,:]
df1.reset_index(drop=True, inplace=True)

#Calculate time
df1.loc[:,'Time']=df1['Dtime'].cumsum()

#Remove extra Columns
df1=df1.drop(columns=['F','E','dE','Distance','Dtime'])
#
#Reorganize dataframe
df1 = df1[['Time','X', 'Y', 'Z','laser']]


#save to inp file
df1.to_csv(filename+'_event_series.inp', index=False, header=False)