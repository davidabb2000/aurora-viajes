import asyncio
from datetime import date, timedelta
from sqlalchemy import select
from src.core.base_datos import Base, motor, FabricaDeSesiones
from src.core.seguridad import hashear_contrasena
from src.models.viajes import (
    Rol, Pais, TipoTurismo, EstadoReserva, Usuario, 
    Destino, Paquete, Salida
)

async def poblar():
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    async with FabricaDeSesiones() as sesion:
        # Verificar si ya hay datos
        if await sesion.scalar(select(Rol).limit(1)) is not None:
            print("La base de datos ya está poblada. No se realizarán cambios.")
            return

        print("Poblando datos paramétricos (3FN)...")
        # 1. Roles
        rol_viajero = Rol(nombre="viajero")
        rol_agente = Rol(nombre="agente")
        
        # 2. Estados de Reserva
        est_pendiente = EstadoReserva(nombre="Pendiente_Pago")
        est_pagada = EstadoReserva(nombre="Pagada")
        est_cancelada = EstadoReserva(nombre="Cancelada")
        
        # 3. Países y Tipos de Turismo
        pais_col = Pais(nombre="Colombia")
        pais_mex = Pais(nombre="México")
        tipo_playa = TipoTurismo(nombre="Playa y Descanso")
        tipo_aventura = TipoTurismo(nombre="Aventura Extrema")
        
        sesion.add_all([
            rol_viajero, rol_agente, est_pendiente, est_pagada, 
            est_cancelada, pais_col, pais_mex, tipo_playa, tipo_aventura
        ])
        await sesion.flush() # Guarda temporalmente para obtener los IDs

        print("Creando usuarios de prueba...")
        # 4. Usuarios
        agente = Usuario(
            documento="999999999", nombre="Agente Experto", 
            email="agente@auroraviajes.com", rol_id=rol_agente.id, 
            contrasena_hash=hashear_contrasena("Admin123*")
        )
        viajero = Usuario(
            documento="111111111", nombre="Turista Feliz", 
            email="turista@ejemplo.com", rol_id=rol_viajero.id, 
            contrasena_hash=hashear_contrasena("Viajero123*")
        )
        sesion.add_all([agente, viajero])
        await sesion.flush()

        print("Creando destinos, paquetes y salidas...")
        # 5. Destinos y Paquetes
        cancun = Destino(nombre="Cancún", pais_id=pais_mex.id)
        san_andres = Destino(nombre="San Andrés", pais_id=pais_col.id)
        sesion.add_all([cancun, san_andres])
        await sesion.flush()

        paquete_cancun = Paquete(
            titulo="Escapada Todo Incluido a Cancún", 
            precio_base=1200, 
            destino_id=cancun.id, 
            tipo_turismo_id=tipo_playa.id
        )
        sesion.add(paquete_cancun)
        await sesion.flush()

        # 6. Salidas (Fechas específicas)
        hoy = date.today()
        salida_1 = Salida(
            paquete_id=paquete_cancun.id, 
            fecha_salida=hoy + timedelta(days=30), 
            fecha_retorno=hoy + timedelta(days=37), 
            cupos_totales=20, 
            cupos_disponibles=20
        )
        sesion.add(salida_1)
        
        await sesion.commit()
        print("¡Base de datos poblada con éxito!")

if __name__ == '__main__':
    asyncio.run(poblar())