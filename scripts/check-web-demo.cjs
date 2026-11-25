const assert = require('node:assert/strict');
const { chromium } = require('playwright');

async function check() {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ baseURL: 'http://127.0.0.1:8010' });
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));

    await page.goto('/auth/');
    await page.getByLabel('Электронная почта').fill('demo@example.com');
    await page.getByLabel('Пароль').fill('testops-demo-2026');
    await page.locator('#auth-form button').click();
    await page.getByText('Демонстрационный режим · тестовые прогоны и ответы').waitFor();
    await page.getByRole('link', { name: 'Пайплайны', exact: true }).click();
    await page.getByRole('link', { name: /Тесты веб-клиента/ }).click();
    await page.locator('#start-pipeline').click();
    await page.waitForURL(/\/runs\/\d+$/);
    const originalUrl = page.url();
    const originalId = originalUrl.split('/').at(-1);
    await page.locator('#run-info').getByText('Ошибка', { exact: true }).waitFor();
    await page.getByRole('link', { name: /Сборка и тесты веб-клиента/ }).click();
    await page.locator('#load-log').click();
    await page.getByText(/1 failed, 4 passed/).waitFor();
    const log = await page.locator('#job-log').textContent();

    await page.goto(originalUrl);
    await page.getByRole('link', { name: 'Создать карточку сбоя' }).click();
    const title = 'Сохранение карточки вернуло 504';
    await page.getByLabel('Краткое название сбоя').fill(title);
    await page.getByLabel('Фактический результат').fill('HTTP 504');
    await page.locator('#diag-file').setInputFiles({
      name: 'web-ci.log', mimeType: 'text/plain', buffer: Buffer.from(log),
    });
    await page.getByRole('button', { name: 'Сохранить сессию' }).click();
    await page.waitForURL(/\/diagnostics\/\d+$/);
    const sessionUrl = page.url();
    await page.getByRole('heading', { name: title }).waitFor();
    await page.getByRole('button', { name: 'Повторить связанный прогон' }).click();
    await page.waitForURL(/\/runs\/\d+$/);
    const repeatedId = page.url().split('/').at(-1);
    assert.notEqual(repeatedId, originalId);
    await page.locator('#run-info').getByText('Успешно', { exact: true }).waitFor();

    await page.goto(sessionUrl);
    for (const [runId, status] of [[originalId, 'Сбой'], [repeatedId, 'Успешно']]) {
      await page.locator(`#check-run option[value="${runId}"]`).waitFor({ state: 'attached' });
      await page.getByLabel('Завершённый повторный прогон').selectOption(runId);
      await page.getByRole('button', { name: 'Записать результат CI' }).click();
      await page.locator('#diagnostic-checks').getByText(status, { exact: true }).waitFor();
    }
    await page.getByRole('button', { name: 'Подготовить черновик' }).click();
    await page.waitForURL(/\/chats\/\d+$/);
    await page.getByText(/Демонстрационный черновик баг-репорта/).waitFor();
    await page.getByText(/Повторный прогон: 5 тестов прошли/).waitFor();
    const download = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Скачать как текст' }).click();
    assert.equal((await download).suggestedFilename(), 'testops-response.txt');

    await page.goto(sessionUrl);
    await page.getByRole('button', { name: 'Отметить решённым' }).click();
    await page.locator('#diagnostic-card').getByText('Решён', { exact: true }).waitFor();
    await page.reload();
    await page.locator('#diagnostic-card').getByText('Решён', { exact: true }).waitFor();
    assert.deepEqual(errors, []);
    console.log('Web demo: login → failed CI → diagnostic → successful repeat → report → resolved');
  } finally {
    await browser.close();
  }
}

check().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
