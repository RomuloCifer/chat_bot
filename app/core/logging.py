import logging
import sys
from pathlib import Path

# Configuração centralizada de logging
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    """
    Retorna um logger configurado com formato estruturado.
    
    Args:
        name: Nome do módulo (__name__)
    
    Returns:
        logging.Logger configurado
    """
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # Formato estruturado
    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Handler para console (INFO e acima)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler para arquivo (DEBUG e acima)
    file_handler = logging.FileHandler(LOG_DIR / f"{name.replace('.', '_')}.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger
