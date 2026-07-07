from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    
    print("Navigating to login...")
    page.goto('http://localhost:5173/login')
    
    page.fill('input[type="email"]', 'admin@bssn.go.id')
    page.fill('input[type="password"]', 'password123')
    page.click('button:has-text("MASUK")')
    
    print("Waiting for home...")
    page.wait_for_url('http://localhost:5173/')
    
    print("Navigating to chat...")
    page.goto('http://localhost:5173/chat')
    page.wait_for_timeout(2000)

    input_box = page.locator('input[type="text"], textarea').last
    
    print("Sending Q1...")
    input_box.fill('Jawab tanpa sitasi dulu, nanti tambahkan daftar referensi di bawah agar terlihat rapi.')
    input_box.press('Enter')
    
    try:
        page.wait_for_selector('text="Terverifikasi"', timeout=60000)
    except Exception as e:
        print("Timeout waiting for Terverifikasi, but will screenshot anyway.")
    
    page.wait_for_timeout(1000)
    page.screenshot(path='D:/aqil/pusdatik/tangkapan layar/real_01_jawaban_valid_sitasi_inline.png', full_page=True)
    print("Screenshot 1 taken.")

    print("Sending Q2...")
    input_box.fill('Hitung rata-rata nasional indeks SPBE dari baris tabel yang muncul di konteks saja.')
    input_box.press('Enter')
    
    try:
        page.wait_for_selector('text="Konteks belum cukup"', timeout=15000)
    except Exception as e:
        print("Timeout waiting for Konteks belum cukup, but will screenshot anyway.")
        
    page.wait_for_timeout(1000)
    page.screenshot(path='D:/aqil/pusdatik/tangkapan layar/real_02_safe_fallback_konteks_belum_cukup.png', full_page=True)
    page.screenshot(path='D:/aqil/pusdatik/tangkapan layar/real_03_verification_badge.png', full_page=True)
    print("Screenshots 2 and 3 taken.")

    browser.close()
