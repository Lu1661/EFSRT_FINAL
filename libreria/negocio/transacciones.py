def escribir(db, operation):
    try:
        resultado = operation()
        db.commit()
        return resultado
    except Exception:
        db.rollback()
        raise
