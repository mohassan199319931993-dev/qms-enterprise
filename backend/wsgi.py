from app import create_app

app = create_app()

# لو create_app بيرجع tuple
if isinstance(app, tuple):
    app = app[0]

application = app
