import csv
import threading
import time

from conexion import conectar_mysql
import mysql.connector
# import _mysql_connector

id=[]
nombre=[]
apellido=[]
edad=[]
sexo=[]
PAS=[]
PAD=[]
FC=[]

with open('datos.csv','r',encoding="utf-8-sig",newline="") as archivo:
    lector=csv.reader(archivo)
    next(lector)

    for fila in lector:
        id.append(int( fila[0]))
        nombre.append(str( fila[1]))
        apellido.append(str( fila[2]))
        edad.append(int( fila[3]))
        sexo.append(str( fila[4]))
        PAS.append(float( fila[5]))
        PAD.append(float( fila[6]))
        FC.append(float( fila[7]))
print("Dataset cargado correctamente")
print("Numero de elementos cargados: ", len(id))

PAM=[0.0] *len(id)
presionPulso=[0.0]*len(id)
indiceChoque=[0.0]*len(id)
# Rango de datos
inicio0=0
fin0=2000
inicio1=2000
fin1=4000
inicio2=4000
fin2=6000
#definiendo funciones para los hilos
def convertir_PAM1():
    for i in range(inicio0,fin0):
        PAM[i]=(PAS[i]+2*PAD[i])/3
def convertir_PAM2():
    for i in range(inicio1,fin1):
        PAM[i]=(PAS[i]+2*PAD[i])/3
def convertir_PAM3():
    for i in range(inicio2,fin2):
        PAM[i]=(PAS[i]+2*PAD[i])/3


h1= threading.Thread(target=convertir_PAM1)
h2= threading.Thread(target=convertir_PAM2)
h3= threading.Thread(target=convertir_PAM3)

inicio=time.perf_counter_ns()
# Utilizando los joins y creando los hilos a la vez
h1.start()
h2.start()
h3.start()

h1.join()
h2.join()
h3.join()

fin=time.perf_counter_ns()

tiempo=(fin-inicio)/1000000

for i in range(len(id)):
    print("\n-------------------------------\n")
    print("Registro: ", id[i], "\n")
    print("Nombre: ", nombre[i],'\t',"Apellido: ",apellido[i],'\t',"Edad: ",edad[i],'\t',"Sexo: ",sexo[i])
    print("PAS: ", PAS[i],'\t',"PAD: ",PAD[i],'\t',"FC: ",FC[i],'\n')
    print("PAM: ", PAM[i],'\n')

    
print("\n-------------------------------\n")
print("Primer registro", id[0])
print("Ultimo registro", id[-1])
print("Total registros", len(id))

print(f"Tiempo de procesamiento: {tiempo:.4f} ms\n")

#conectar mySQL y guardas datos a la base de datos

conexion=None
cursor=None

try:
    conexion=conectar_mysql()
    cursor= conexion.cursor()
    print("Conexion exitosa de la base de Datos MySQL")
    sql_original="""
        INSERT INTO registro_paciente(id,nombre,apellido,edad,sexo,PAS,PAD,FC)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE nombre= VALUES(nombre),apellido= VALUES(apellido),edad= VALUES(edad),sexo= VALUES(sexo),PAS= VALUES(PAS),PAD= VALUES(PAD),FC= VALUES(FC)
    """
    sql_resultado="""
        INSERT  INTO registro_resultados(id_paciente,PAM,tiempo_microsegundos)
        VALUES(%s,%s,%s)
        ON DUPLICATE KEY UPDATE id_paciente= VALUES(id_paciente),PAM= VALUES(PAM),tiempo_microsegundos= VALUES(tiempo_microsegundos)
                
        
    """
    for i in range(len(id)):
        cursor.execute(sql_original, (id[i],nombre[i],apellido[i],edad[i],sexo[i],PAS[i],PAD[i],FC[i]))
        cursor.execute(sql_resultado,(id[i],PAM[i],tiempo))
    conexion.commit()
    print("Datos guardados correctamente: ",len(id))
    print("Registros guardados: ",len(id))
except mysql.connector.Error as error:
    if conexion is not None:
        conexion.rollback()
    print(f"Error al guardas los datos en la base de datos: {error}")
finally:
    if cursor is not None:
        cursor.close()
    if cursor is not None and conexion .is_connected():
        conexion.close()
