import { chromium, expect } from '@playwright/test';
import { readFileSync, mkdirSync } from 'node:fs';
const accounts=JSON.parse(readFileSync('../assurex-backend/private/testing-kit-20260927-161856/accounts.json','utf8'));
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[]; page.on('pageerror',e=>errors.push(e.message));
try {
await page.goto('http://127.0.0.1:5180/sign-in');
await page.getByLabel('Email address').fill(accounts.users.customer.email);
await page.getByLabel('Password',{exact:true}).fill(accounts.password);
await page.getByRole('button',{name:'Login',exact:true}).click();
await page.waitForURL('**/overview');
await page.goto('http://127.0.0.1:5180/products');
await page.locator('.product-card').first().waitFor();
mkdirSync('reports/product-ui',{recursive:true});
await page.screenshot({path:'reports/product-ui/products-desktop.png',fullPage:true});
await page.locator('.product-view').first().click();
await page.locator('.product-summary').waitFor();
await page.getByRole('heading',{name:'Warranty coverage'}).waitFor();
await page.screenshot({path:'reports/product-ui/detail-desktop.png',fullPage:true});
for(const label of ['Warranty','Documents','Service history','Overview']) {
const nav=page.getByRole('navigation',{name:'Product sections'});
await nav.getByRole('link',{name:label,exact:true}).click();
await page.waitForURL('**/' + ({Warranty:'warranty',Documents:'documents','Service history':'history',Overview:'overview'}[label])); await expect(nav.locator('a.active')).toHaveText(label);
}
await page.setViewportSize({width:390,height:844});
await page.screenshot({path:'reports/product-ui/detail-mobile.png',fullPage:true});
if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw Error('Detail overflow');
await page.goto('http://127.0.0.1:5180/products');
await page.locator('.product-card').first().waitFor();
await page.screenshot({path:'reports/product-ui/products-mobile.png',fullPage:true});
if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw Error('List overflow');
if(errors.length) throw Error(errors.join('\n'));
console.log('Real-session desktop/mobile product pages and all four detail tabs passed.');
} finally {await browser.close();}


