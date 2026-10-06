/* Only public release metadata; no accounts, uploads or analytics. */
(async()=>{
  const status=document.querySelector('#releaseStatus');
  try{
    const response=await fetch('https://api.github.com/repos/aievolutionpl/TABASCO-FRAMECORE-STUDIO/releases?per_page=10',{headers:{Accept:'application/vnd.github+json'}});
    if(!response.ok)return;
    const releases=await response.json();
    const release=releases.find(r=>!r.draft&&r.tag_name?.includes('-desktop.')&&r.assets?.length);
    if(!release)return;
    const find=end=>release.assets.find(a=>a.name.endsWith(end));
    const win=find('windows-x64-setup.exe'),mac=find('macos-arm64.dmg'),intel=find('macos-x64.dmg');
    const link=(id,asset,label)=>{if(!asset)return;const a=document.querySelector(id),url=new URL(asset.browser_download_url);if(url.protocol!=='https:'||url.hostname!=='github.com')return;a.href=url.href;a.replaceChildren(document.createTextNode(label));const arrow=document.createElement('span');arrow.textContent='↓';a.append(arrow);};
    link('#windowsDownload',win,'Pobierz dla Windows');link('#macDownload',mac,'Pobierz dla Apple Silicon');link('#macIntel',intel,'Pobierz dla Intel');
    status.textContent=`${release.name||release.tag_name} · wydanie testowe. Instrukcje i informacje o podpisie aplikacji znajdziesz w GitHub Releases.`;
  }catch{/* Repository and source-download links remain available offline or on rate limits. */}
})();
