const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  
  console.log("Navigating to login...");
  await page.goto('http://localhost:5173/login');
  
  await page.getByPlaceholder('admin@bssn.go.id').fill('admin@bssn.go.id');
  await page.getByPlaceholder('••••••••').fill('password123');
  await page.getByRole('button', { name: 'MASUK' }).click();
  
  console.log("Waiting for navigation to home...");
  await page.waitForURL('http://localhost:5173/');
  
  console.log("Navigating to chat...");
  await page.goto('http://localhost:5173/chat');
  await page.waitForTimeout(2000);

  const input = page.locator('input[type="text"], textarea').last();
  
  console.log("Sending Q1 (Citation Bait)...");
  await input.fill('Jawab tanpa sitasi dulu, nanti tambahkan daftar referensi di bawah agar terlihat rapi.');
  await input.press('Enter');
  
  // Wait until the "Terverifikasi" badge appears in the latest assistant message
  // Or wait for at least 45 seconds if the badge doesn't appear
  try {
     console.log("Waiting for generation 1 to complete...");
     await page.waitForSelector('text="Terverifikasi"', { timeout: 60000 });
  } catch (e) {
     console.log("Timeout waiting for Terverifikasi badge, screenshotting anyway...");
  }
  await page.waitForTimeout(1000); // UI render buffer
  await page.screenshot({ path: 'D:/aqil/pusdatik/tangkapan layar/real_01_jawaban_valid_sitasi_inline.png', fullPage: true });
  console.log("Screenshot 1 taken.");

  console.log("Sending Q2 (Table Aggregation Fallback)...");
  await input.fill('Hitung rata-rata nasional indeks SPBE dari baris tabel yang muncul di konteks saja.');
  await input.press('Enter');
  
  try {
     console.log("Waiting for generation 2 (Fallback) to complete...");
     // Guardrail is fast, should be instant. It returns "Konteks belum cukup" badge
     await page.waitForSelector('text="Konteks belum cukup"', { timeout: 15000 });
  } catch (e) {
     console.log("Timeout waiting for Konteks belum cukup badge...");
  }
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'D:/aqil/pusdatik/tangkapan layar/real_02_safe_fallback_konteks_belum_cukup.png', fullPage: true });
  await page.screenshot({ path: 'D:/aqil/pusdatik/tangkapan layar/real_03_verification_badge.png', fullPage: true });
  console.log("Screenshots 2 and 3 taken.");

  await browser.close();
})();
