(function () {
  function normalizeStatus(raw) {
    var v = String(raw || '').trim().toLowerCase();
    if (v === 'verified' || v === 'pending' || v === 'rejected') return v;
    return 'pending';
  }

  function read(profile, role) {
    var r = String(role || '').toLowerCase();
    if (r === 'buyer') return normalizeStatus(profile && profile.verification_status_db);
    return normalizeStatus(profile && profile.certification_status_db);
  }

  function readAdminCombined(user) {
    var cert = normalizeStatus(user && user.certification_status_db);
    var buyer = normalizeStatus(user && user.buyer_verification_status_db);
    if (cert === 'rejected' || buyer === 'rejected') return 'rejected';
    if (cert === 'verified' || buyer === 'verified') return 'verified';
    return 'pending';
  }

  window.SokoStatus = window.SokoStatus || {};
  window.SokoStatus.normalize = normalizeStatus;
  window.SokoStatus.read = read;
  window.SokoStatus.readAdminCombined = readAdminCombined;
})();
