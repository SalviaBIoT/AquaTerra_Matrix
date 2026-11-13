import pandas as pd
import os
import json


class GestorDatos:
    def __init__(self):
        # Calculamos la ruta relativa para que funcione en cualquier equipo
        carpeta_actual = os.path.dirname(os.path.abspath(__file__))
        raiz_proyecto = os.path.dirname(carpeta_actual)

        # Rutas a los archivos de datos
        self.ruta_datos = os.path.join(raiz_proyecto, 'data')
        self.ruta_parcelas = os.path.join(self.ruta_datos, 'parcelas.csv')
        self.ruta_riegos = os.path.join(self.ruta_datos, 'riegos.json')

    def cargar_parcelas(self):
        """Lee el archivo CSV y devuelve la tabla de datos."""
        try:
            tabla_datos = pd.read_csv(self.ruta_parcelas)
            # Aseguramos que el ID sea un número entero para evitar errores al buscar
            if 'id' in tabla_datos.columns:
                tabla_datos['id'] = tabla_datos['id'].astype(int)
            print("DATOS CARGADOS CORRECTAMENTE")
            return tabla_datos
        except FileNotFoundError:
            print("ERROR: NO SE ENCUENTRA EL ARCHIVO PARCELAS.CSV")
            return None
        except Exception as e:
            print(f"ERROR AL LEER CSV: {e}")
            return None

    def guardar_parcela(self, datos_parcela):
        """Agrega un nuevo registro al final del archivo CSV."""
        try:
            tabla_datos = pd.read_csv(self.ruta_parcelas)

            # Generamos un ID consecutivo automático
            id_nuevo = 1
            if not tabla_datos.empty:
                id_nuevo = tabla_datos['id'].max() + 1
            datos_parcela['id'] = id_nuevo

            # Convertimos el diccionario a una fila de tabla y la pegamos al final
            fila_nueva = pd.DataFrame([datos_parcela])
            tabla_actualizada = pd.concat([tabla_datos, fila_nueva], ignore_index=True)

            # Guardamos los cambios en el archivo sin crear índices extra
            tabla_actualizada.to_csv(self.ruta_parcelas, index=False)
            return True
        except Exception as e:
            print(f"ERROR AL GUARDAR: {e}")
            return False

    def actualizar_parcela(self, id_objetivo, datos_nuevos):
        """Busca una fila por ID y actualiza sus valores."""
        try:
            tabla_datos = pd.read_csv(self.ruta_parcelas)

            # Convertimos IDs a enteros para asegurar una comparación correcta
            tabla_datos['id'] = tabla_datos['id'].astype(int)
            id_objetivo = int(id_objetivo)

            # Verificamos si el ID existe en la tabla
            if id_objetivo in tabla_datos['id'].values:
                filtro = tabla_datos['id'] == id_objetivo

                # Actualizamos cada campo asegurando el tipo de dato correcto
                tabla_datos.loc[filtro, 'nombre'] = str(datos_nuevos['nombre'])
                tabla_datos.loc[filtro, 'cultivo'] = str(datos_nuevos['cultivo'])
                tabla_datos.loc[filtro, 'area'] = float(datos_nuevos['area'])

                # Actualizamos la humedad si viene en los datos nuevos
                if 'humedad' in datos_nuevos:
                    tabla_datos.loc[filtro, 'humedad'] = int(float(datos_nuevos['humedad']))

                tabla_datos.loc[filtro, 'suelo'] = str(datos_nuevos['suelo'])
                tabla_datos.loc[filtro, 'riego_auto'] = str(datos_nuevos['riego_auto'])

                tabla_datos.to_csv(self.ruta_parcelas, index=False)
                print(f"PARCELA {id_objetivo} ACTUALIZADA EN CSV")
                return True
            else:
                print(f"ERROR: ID {id_objetivo} NO ENCONTRADO")
                return False
        except Exception as e:
            print(f"ERROR FALLO AL ACTUALIZAR: {e}")
            return False

    def eliminar_parcela(self, id_objetivo):
        """Borra una fila y reordena los IDs para no dejar huecos."""
        try:
            tabla_datos = pd.read_csv(self.ruta_parcelas)

            # Filtramos para quedarnos con todo MENOS el ID que queremos borrar
            tabla_filtrada = tabla_datos[tabla_datos['id'] != id_objetivo]

            # Si quedan datos, recalculamos los IDs desde 1
            if not tabla_filtrada.empty:
                tabla_filtrada = tabla_filtrada.copy()
                tabla_filtrada['id'] = range(1, len(tabla_filtrada) + 1)

            tabla_filtrada.to_csv(self.ruta_parcelas, index=False)
            return True
        except Exception as e:
            print(f"ERROR FALLO AL ELIMINAR: {e}")
            return False

    def registrar_riego(self, datos_riego):
        """Guarda un registro histórico en el archivo JSON."""
        try:
            lista_riegos = []

            # Intentamos leer el historial existente si el archivo existe
            if os.path.exists(self.ruta_riegos):
                with open(self.ruta_riegos, 'r', encoding='utf-8') as archivo:
                    try:
                        lista_riegos = json.load(archivo)
                    except json.JSONDecodeError:
                        lista_riegos = []  # Archivo corrupto o vacío, iniciamos lista nueva

            # Agregamos el nuevo evento al final de la lista
            lista_riegos.append(datos_riego)

            # Sobrescribimos el archivo con la lista actualizada
            with open(self.ruta_riegos, 'w', encoding='utf-8') as archivo:
                json.dump(lista_riegos, archivo, indent=4, ensure_ascii=False)

            print("EVENTO DE RIEGO REGISTRADO EN JSON")
            return True

        except Exception as e:
            print(f"ERROR NO SE PUDO GUARDAR EL HISTORIAL DE RIEGO: {e}")
            return False


    def cargar_historial_riegos(self):
        """Lee el archivo JSON de riegos para generar reportes."""
        try:
            if os.path.exists(self.ruta_riegos):
                with open(self.ruta_riegos, 'r', encoding='utf-8') as archivo:
                    return json.load(archivo)
            return []  # Retorna lista vacía si no hay archivo
        except Exception as e:
            print(f"ERROR AL CARGAR HISTORIAL: {e}")
            return []