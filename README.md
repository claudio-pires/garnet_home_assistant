[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository=garnet_home_assistant&category=Integration&owner=claudio-pires)
![Alt text](https://brands.home-assistant.io/garnet_home_assistant/logo.png "a title")
# Garnet Alarm Panels integration for Home Assistant

Integracion de paneles de alarmas domiciliarias [Garnet Technologies](https://www.garnet.com.ar/) en Home Assistant.
Si bien los paneles disponen de alguna posibilidad de disparar automatizaciones, son muy limitadas y desde que posee un panel Garnet en mi casa siempre quise disparar automatizaciones mas complejas como por ejemplo armar la alarma en modo home cuando me voy a dormir, o disparar un panico temporizado cuando entro con el auto en mi garage durante la noche.
No soy programador python y tambien esta es mi primera integracion para Home Assistant asi que sepan disculpar si ven errores groseros. Cualquier sugerencia de mejora es bienvenida.
Esta integracion ha sido probada con un panel PC-732-G con comunicador 500G



## Requerimientos

- Se requiere que el panel esté registrado en [Garnet Control](https://web.garnetcontrol.app/#!/login)
- Se requiere que el panel posea comunicador IP y configurar el monitoreo para que envie mensajes al controlador Home Assistant


## Funcionamiento

- Se conecta a Garnet Control con el identificador de panel y obtiene la informacion completa de la configuracion del panel y el estado inicial
- Posteriormente escucha los mensajes SIA del panel y va actualizando el estado de las entidades
- Los controles ejecutan comandos HTTP provistos por la API HTTP de Garnet Control



## Instalación

### Opción 1: Instalación Manual
1. Descargar la carpeta `garnet_home_assistant` desde la [última release](https://github.com/claudio-pires/garnet_home_assistant/releases/latest)
2. Copiarlo a la carpeta [`carpeta custom_components`](https://developers.home-assistant.io/docs/creating_integration_file_structure/#where-home-assistant-looks-for-integrations)
3. Reiniciar Home Assistant

### Opción 2: Instalación usando HACS  (TBD)
1. Clic en HACS en el menú de Home Assistant
2. Clic en `Integrations`
3. Clic en el botón `EXPLORE & DOWNLOAD REPOSITORIES` 
4. Buscar `Garnet Tech`
5. Click en `DOWNLOAD` 
6. Reiniciar Home Assistant



## Configuración

### Sobre el panel 
1. Crear una cuenta en [Garnet Control](https://web.garnetcontrol.app/#!/register)
2. Registrá tu sistema de alarma, y toma nota del numero de sistema que será necesario para registrar luego la integracion, por ejemplo `a123456789`
3. Tu comunicador debe tener una conexion a la red Wifi funcionando. Es necesario configurar el monitoreo por Wifi y asignar la direccion IP de la receptora con la IP de tu controlador home assistant. Tambien podes ingresar `homeassistant.local`. El puerto debe ser `2123`. Ingresa un numero de abonado. Si el keepalive es diferente de `1` minuto se debe configurar en la integracion. El protocolo debe ser `SDC2`.

### Crear la integracion
1. En Home assistant ir a `Settings`, luego `Devices & services` y hacer clic en el boton `+ ADD INTEGRATION`. Buscar `Garnet` y seleccionar.
2. Ingresar los datos de acceso a `Garnet Control`, el numero de sistema y el numero de abonado. SI el timeout es distinto a 60 segundos reconfigurar.



### Pendientes
- a trama de estado que devuelven los comandos en la API se interpretó en base a prueba y error. Intentaré conseguir documentación oficial para poder terminar algunas funciones. 
- Aun no conozco el tiempo de validez del token, se asumen 10 minutos
- Pendiente implementear funciones para bypassear zonas, pánico demorado, obtener eventos varios (estado de baterías, energía, etc)


## Contribución
- Muchas gracias a [Guido117](https://github.com/Guido117) por su ayuda con la informacion sobre API Garnet
- Son bienvenidas las solicitudes de nuevas funcionalidades y los reportes de bugs! Abrir un [issue en GitHub](https://github.com/claudio-pires/garnet_home_assistant/issues/new/choose).
- Bienvenidos tambien quienes deseen colaborar en el mantenimiento y agregado de nuevas funcionalidades
