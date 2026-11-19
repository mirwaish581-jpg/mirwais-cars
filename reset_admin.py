
from app import db
from werkzeug.security import generate_password_hash

new_password = "Hakimi@2026"

with db() as con:
    con.execute(
        "UPDATE users SET password=? WHERE username=?",
        (generate_password_hash(new_password), "admin")
    )

print("Admin password successfully reset!")
print("Username: admin")
print("Password: Hakimi@2026")
