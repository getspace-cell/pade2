import os
import sys
import time
import subprocess


def restart_system():
    """Полный перезапуск системы с принудительным завершением"""
    print("=" * 60)
    print("🔄 ПОЛНЫЙ ПЕРЕЗАПУСК СИСТЕМЫ")
    print("=" * 60)

    current_pid = os.getpid()
    print(f"🔴 Текущий PID: {current_pid}")

    # Шаг 1: Запускаем новую систему
    print("🚀 Запускаем новую систему...")
    try:
        if os.name == 'nt':  # Windows
            subprocess.Popen([sys.executable, "main.py"],
                             creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:  # Unix/Linux
            subprocess.Popen([sys.executable, "main.py"],
                             start_new_session=True)
        print("✅ Новая система запущена")
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")

    # Шаг 2: Даем время новой системе запуститься
    time.sleep(5)

    # Шаг 3: Принудительно завершаем старую систему
    print("🔴 Завершаем старую систему...")
    if os.name == 'nt':  # Windows
        # Завершаем только текущий процесс и его дочерние процессы
        try:
            subprocess.run(['taskkill', '/F', '/PID', str(current_pid), '/T'],
                           timeout=5, capture_output=True)
            print("✅ Старая система завершена")
        except:
            print("⚠️  Не удалось завершить процесс автоматически")
            sys.exit(0)
    else:  # Unix/Linux
        os._exit(0)


if __name__ == "__main__":
    restart_system()