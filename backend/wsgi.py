from app import create_app

# create_app بيرجع (app, socketio)
app, socketio = create_app()

application = app
