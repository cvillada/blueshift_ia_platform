const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch({headless:"new"});
  const page = await browser.newPage();
  const path = require('path').resolve('blueshift-ia-platform.html');
  await page.goto('file://' + path, {waitUntil:'networkidle0'});
  await page.pdf({
    path: 'blueshift-ia-platform.pdf',
    format: 'A4',
    printBackground: true,
    margin: {top:'10mm', bottom:'10mm', left:'10mm', right:'10mm'}
  });
  await browser.close();
  console.log('PDF gerado: blueshift-ia-platform.pdf');
})();
