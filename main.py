import tkinter as tk
from tkinter import scrolledtext, messagebox, OptionMenu
import threading
import time
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from bs4 import BeautifulSoup
import Levenshtein

# Ses ve bildirim kütüphanelerini içe aktar
try:
    from playsound import playsound
    SOUND_AVAILABLE = True
except ImportError:
    SOUND_AVAILABLE = False
    print("playsound kütüphanesi bulunamadı. Sesli uyarılar çalışmayacaktır. Lütfen 'pip install playsound' komutunu çalıştırın.")

try:
    from plyer import notification
    NOTIFICATION_AVAILABLE = True
except ImportError:
    NOTIFICATION_AVAILABLE = False
    print("plyer kütüphanesi bulunamadı. Masaüstü bildirimleri çalışmayacaktır. Lütfen 'pip install plyer' komutunu çalıştırın.")

class WebsiteMonitorApp:
    def __init__(self, master):
        self.master = master
        master.title("Web Sitesi İzleyici")
        master.geometry("600x680")

        self.driver = None
        self.is_monitoring = False
        self.monitor_thread = None
        self.interval = 15
        self.sound_file = "alert.mp3"
        self.change_threshold = 5.0 # Ondalıklı değer için 5.0 olarak güncellendi

        # --- Arayüz Elemanları ---
        tk.Label(master, text="URL:").pack(pady=5)
        self.url_entry = tk.Entry(master, width=60)
        self.url_entry.pack()
        self.url_entry.insert(0, "https://example.com")

        tk.Label(master, text="Tarayıcı Seçin:").pack(pady=5)
        self.browser_options = ["Chrome", "Firefox", "Edge"]
        self.browser_var = tk.StringVar(master)
        self.browser_var.set(self.browser_options[0])
        self.browser_menu = OptionMenu(master, self.browser_var, *self.browser_options)
        self.browser_menu.pack()

        tk.Label(master, text="Yenileme Aralığı (saniye):").pack(pady=5)
        self.interval_entry = tk.Entry(master, width=10)
        self.interval_entry.insert(0, "15")
        self.interval_entry.pack()

        tk.Label(master, text="Değişim Eşiği (ör. %5 için 5 veya %0.5 için 0.5 girin):").pack(pady=5)
        self.threshold_entry = tk.Entry(master, width=10)
        self.threshold_entry.insert(0, "5.0")
        self.threshold_entry.pack()
        
        # Canlı durum göstergesi
        self.status_label = tk.Label(master, text="Durum: Bekliyor...", font=("Arial", 12), fg="blue")
        self.status_label.pack(pady=10)
        
        self.open_browser_button = tk.Button(master, text="Tarayıcıyı Aç", command=self.open_browser)
        self.open_browser_button.pack(pady=10)

        self.start_monitor_button = tk.Button(master, text="İzlemeyi Başlat", command=self.start_monitoring, state=tk.DISABLED)
        self.start_monitor_button.pack(pady=5)

        self.stop_button = tk.Button(master, text="İzlemeyi Durdur", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_button.pack(pady=5)

        tk.Label(master, text="Durum ve Loglar:").pack(pady=5)
        self.log_area = scrolledtext.ScrolledText(master, width=70, height=20, wrap=tk.WORD)
        self.log_area.pack(pady=10)

    def log_message(self, message):
        """GUI'deki log alanına mesaj yazar."""
        self.log_area.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_area.see(tk.END)

    def update_status_label(self, message, color):
        """Durum etiketini günceller ve renk atar."""
        self.status_label.config(text=message, fg=color)

    def play_alert_sound(self):
        """Bir değişiklik tespit edildiğinde uyarı sesi çalar."""
        if SOUND_AVAILABLE and os.path.exists(self.sound_file):
            try:
                threading.Thread(target=playsound, args=(self.sound_file,), daemon=True).start()
                self.log_message("Uyarı sesi çalınıyor...")
            except Exception as e:
                self.log_message(f"Ses çalınırken bir hata oluştu: {e}")
        elif not SOUND_AVAILABLE:
            self.log_message("playsound kütüphanesi bulunamadı.")
        elif not os.path.exists(self.sound_file):
            self.log_message(f"Ses dosyası bulunamadı: '{self.sound_file}'")
    
    def send_notification(self, title, message):
        """Masaüstü bildirimi gönderir."""
        if NOTIFICATION_AVAILABLE:
            try:
                notification.notify(
                    title=title,
                    message=message,
                    app_name="Web Sitesi İzleyici",
                    timeout=10
                )
            except Exception as e:
                self.log_message(f"Bildirim gönderilirken bir hata oluştu: {e}")
        else:
            self.log_message("plyer kütüphanesi bulunamadı. Bildirim gönderilemiyor.")

    def open_browser(self):
        """Seçilen tarayıcıyı başlatır ve URL'ye gider."""
        url = self.url_entry.get()
        if not url:
            messagebox.showerror("Hata", "Lütfen bir URL girin.")
            return

        self.open_browser_button.config(state=tk.DISABLED)
        self.update_status_label("Durum: Tarayıcı Başlatılıyor...", "blue")
        self.log_message("Tarayıcı başlatılıyor ve URL'ye gidiliyor...")
        
        try:
            selected_browser = self.browser_var.get()
            
            if selected_browser == "Chrome":
                service = ChromeService(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service)
            elif selected_browser == "Firefox":
                service = FirefoxService(GeckoDriverManager().install())
                self.driver = webdriver.Firefox(service=service)
            elif selected_browser == "Edge":
                service = EdgeService(EdgeChromiumDriverManager().install())
                self.driver = webdriver.Edge(service=service)
            else:
                raise ValueError("Geçersiz tarayıcı seçimi.")

            self.driver.get(url)
            self.update_status_label("Durum: Hazır (Manuel Giriş Gerekiyor)", "orange")
            self.log_message("Tarayıcı başarıyla açıldı. Lütfen manuel olarak giriş yapın ve ardından 'İzlemeyi Başlat' butonuna basın.")
            self.start_monitor_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
        except Exception as e:
            self.log_message(f"Tarayıcıyı başlatırken bir hata oluştu: {e}")
            self.update_status_label("Durum: Hata Oluştu", "red")
            self.open_browser_button.config(state=tk.NORMAL)

    def start_monitoring(self):
        """İzleme işlemini başlatır ve GUI'yi günceller."""
        if not self.driver:
            messagebox.showerror("Hata", "Lütfen önce 'Tarayıcıyı Aç' butonuna tıklayın.")
            return

        try:
            self.interval = int(self.interval_entry.get())
            # Değişim eşiği artık ondalıklı olabilir.
            # Virgül varsa noktaya çevirerek float'a dönüştürür.
            threshold_str = self.threshold_entry.get().replace(',', '.')
            self.change_threshold = float(threshold_str)
        except ValueError:
            messagebox.showerror("Hata", "Lütfen geçerli bir sayı girin (saniye ve eşik için).")
            return

        self.open_browser_button.config(state=tk.DISABLED)
        self.start_monitor_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.is_monitoring = True
        
        self.log_message("İzleme işlemi başlatılıyor...")
        self.update_status_label("Durum: İzleniyor...", "green")
        
        self.monitor_thread = threading.Thread(target=self.monitor_process, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        """İzleme işlemini durdurur ve tarayıcıyı kapatır."""
        self.is_monitoring = False
        self.log_message("İzleme işlemi durduruluyor...")
        self.stop_button.config(state=tk.DISABLED)
        self.start_monitor_button.config(state=tk.NORMAL)
        self.open_browser_button.config(state=tk.NORMAL)
        
        if self.driver:
            self.driver.quit()
            self.driver = None
        self.log_message("Tarayıcı kapatıldı ve program durduruldu.")
        self.update_status_label("Durum: Durduruldu", "red")

    def save_page_backup(self, page_source):
        """HTML sayfasını tarih ve saat bilgisiyle yedekler."""
        backup_folder = "page_backups"
        if not os.path.exists(backup_folder):
            os.makedirs(backup_folder)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{backup_folder}/backup_{timestamp}.html"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(page_source)
        self.log_message(f"Sayfa içeriği yedeklendi: {filename}")
        self.update_status_label("Durum: DEĞİŞİKLİK TESPİT EDİLDİ!", "red")

    def get_clean_html(self, html_source):
        """HTML'den temiz bir metin elde eder."""
        soup = BeautifulSoup(html_source, 'html.parser')
        for tag in soup(['script', 'style', 'meta', 'link']):
            tag.decompose()
        return str(soup)

    def compare_html_by_diff(self, old_html, new_html):
        """İki HTML dizesi arasındaki Levenşayn mesafesini hesaplar ve yüzde olarak döndürür."""
        old_text = ' '.join(BeautifulSoup(old_html, 'html.parser').stripped_strings)
        new_text = ' '.join(BeautifulSoup(new_html, 'html.parser').stripped_strings)

        distance = Levenshtein.distance(old_text, new_text)
        max_len = max(len(old_text), len(new_text))
        if max_len == 0:
            return 0.0
        
        return (distance / max_len) * 100.0

    def monitor_process(self):
        try:
            self.log_message("Sayfa içeriği hazırlanıyor...")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            initial_html = self.get_clean_html(self.driver.page_source)
            
            while self.is_monitoring:
                self.log_message("Sayfa kontrol ediliyor...")
                self.update_status_label("Durum: Kontrol Ediliyor...", "blue")
                self.driver.refresh()
                
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )

                new_html = self.get_clean_html(self.driver.page_source)
                
                change_detected = False
                change_percentage = self.compare_html_by_diff(initial_html, new_html)

                if change_percentage >= self.change_threshold:
                    self.log_message(f"\n*** DİKKAT: Sayfa içeriği değişti! (%{change_percentage:.2f}) ***")
                    self.log_message("Detaylı inceleme için yedekleme yapılıyor.")
                    self.save_page_backup(new_html)
                    initial_html = new_html
                    change_detected = True
                    self.send_notification("Sayfa Değişikliği", f"İzlenen web sayfasında %{change_percentage:.2f} oranında içerik değişikliği tespit edildi.")
                
                try:
                    popup_element = self.driver.find_element(By.ID, "modal-popup")
                    if popup_element.is_displayed():
                        self.log_message("\n*** DİKKAT: Yeni bir açılır pencere (popup) tespit edildi! ***")
                        self.save_page_backup(new_html)
                        change_detected = True
                        self.send_notification("Yeni Popup", "İzlenen web sayfasında yeni bir açılır pencere (popup) belirdi.")
                except NoSuchElementException:
                    pass

                if change_detected:
                    self.play_alert_sound()
                    self.update_status_label("Durum: DEĞİŞİKLİK TESPİT EDİLDİ!", "red")
                else:
                    self.log_message(f"Değişim tespit edilmedi. (%{change_percentage:.2f}). Bekleniyor...")
                    self.update_status_label("Durum: İzleniyor...", "green")
                
                time.sleep(self.interval)

        except Exception as e:
            self.log_message(f"Bir hata oluştu: {e}")
            self.stop_monitoring()

if __name__ == "__main__":
    root = tk.Tk()
    app = WebsiteMonitorApp(root)
    root.mainloop()