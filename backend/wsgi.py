from app import create_app

# create_app بيرجع (app, socketio)
app, socketio = create_app()

application = app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
