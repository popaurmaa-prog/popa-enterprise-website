const config = window.SITE_CONFIG || {};
const nav = document.getElementById('nav');
const toggle = document.querySelector('.menu-toggle');
toggle.addEventListener('click', () => { const open = toggle.getAttribute('aria-expanded') === 'true'; toggle.setAttribute('aria-expanded', String(!open)); nav.classList.toggle('open', !open); });
nav.querySelectorAll('a').forEach(a => a.addEventListener('click', () => { nav.classList.remove('open'); toggle.setAttribute('aria-expanded','false'); }));
document.getElementById('year').textContent = new Date().getFullYear();
const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const validUrl = value => { try { const u = new URL(value); return ['https:','http:'].includes(u.protocol) ? u.href : ''; } catch { return ''; } };
const ventures = document.getElementById('venture-list');
(config.ventures || []).forEach((v,i) => { const url=validUrl(v.url); const el=document.createElement('article'); el.className='venture-card'; el.innerHTML=`<span class="venture-num">0${i+1} / ${escapeHtml(v.category)}</span><h3>${escapeHtml(v.name)}</h3><p>${escapeHtml(v.description)}</p>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(v.linkText || 'Visit website')} ↗</a>` : `<span class="not-live">${escapeHtml(v.linkText || 'Coming soon')}</span>`}${validUrl(v.secondaryUrl) ? `<a style="display:block;margin-top:0;padding-top:12px" href="${escapeHtml(validUrl(v.secondaryUrl))}" target="_blank" rel="noopener noreferrer">${escapeHtml(v.secondaryLinkText || 'Follow on social media')} ↗</a>` : ''}`; ventures.appendChild(el); });
if(config.contactEmail && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(config.contactEmail)) {
  const form=document.getElementById('inquiry-form');
  form.hidden=false;
  document.getElementById('contact-fallback').hidden=true;
  form.addEventListener('submit', event => {
    event.preventDefault();
    if(!form.reportValidity()) return;
    const values=new FormData(form);
    const subject=`Enterprise inquiry: ${values.get('topic')}`;
    const body=`Name: ${values.get('name')}\nReply email: ${values.get('email')}\nInquiry type: ${values.get('topic')}\n\n${values.get('message')}`;
    window.location.href=`mailto:${config.contactEmail}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  });
}
