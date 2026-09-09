import stripe
from fastapi import APIRouter, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.core.configuracion import configuracion
from src.dependencias import SesionDep, UsuarioLogueado
from src.models.viajes import Salida, Reserva, EstadoReserva

stripe.api_key = configuracion.stripe_secret_key
router = APIRouter(prefix='/reservas', tags=['Reservas y Pagos'])

@router.post('', summary="Crear reserva e iniciar pago")
async def crear_reserva_y_pago(salida_id: int, sesion: SesionDep, usuario: UsuarioLogueado):
    # 1. Verificar la salida y cupos
    consulta_salida = select(Salida).options(joinedload(Salida.paquete)).where(Salida.id == salida_id)
    salida = await sesion.scalar(consulta_salida)
    
    if not salida or salida.cupos_disponibles <= 0:
        raise HTTPException(status_code=409, detail="No hay cupos disponibles para esta fecha.")
        
    # 2. Buscar el estado "Pendiente_Pago" (Asumiendo ID 1)
    estado_pendiente = await sesion.get(EstadoReserva, 1)
    
    # 3. Restar cupo temporalmente y crear reserva
    salida.cupos_disponibles -= 1
    nueva_reserva = Reserva(
        usuario_id=usuario.id, 
        salida_id=salida.id, 
        estado_id=estado_pendiente.id
    )
    sesion.add(nueva_reserva)
    await sesion.commit()
    await sesion.refresh(nueva_reserva)
    
    # 4. Generar sesión de pago en Stripe
    if configuracion.stripe_secret_key:
        sesion_stripe = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': salida.paquete.titulo},
                    'unit_amount': salida.paquete.precio_base * 100, # Stripe usa centavos
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"http://localhost:5173/exito?reserva={nueva_reserva.id}",
            cancel_url=f"http://localhost:5173/cancelado",
            client_reference_id=str(nueva_reserva.id)
        )
        url_pago = sesion_stripe.url
    else:
        url_pago = "https://mock-pago-local.com"

    return {
        "mensaje": "Reserva creada. Procede al pago para confirmarla.",
        "reserva_id": nueva_reserva.id,
        "url_pago": url_pago
    }