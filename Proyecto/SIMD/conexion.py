import mysql.connector

def conectar_mysql():

    conexion = mysql.connector.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="",
        database="proyecto_simd"
    )

    return conexion

if __name__ == "__main__":
    try:
        conexion = conectar_mysql()
        if conexion.is_connected():
            print("Conexión exitosa a la base de datos MySQL")
            print("BASE DE DATOS Mbasemisd ")
            conexion.close()
    except mysql.connector.Error as error:
        print(f"Error al conectar a la base de datos: {error}")