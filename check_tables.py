from sqlalchemy import inspect

from backend.models_temp import engine

print(f"Database: {engine.url.render_as_string(hide_password=True)}")
print('Tables in database:')
for name in inspect(engine).get_table_names():
    print(' -', name)
