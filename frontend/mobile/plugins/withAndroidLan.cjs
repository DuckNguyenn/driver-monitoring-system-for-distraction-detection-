const {withAndroidManifest} = require('expo/config-plugins');

// The user enters the API address, so its LAN hostname is not known at build time.
// Android release builds otherwise block the existing HTTP API.
module.exports = function withAndroidLan(config) {
  return withAndroidManifest(config, mod => {
    const application = mod.modResults.manifest.application?.[0];
    if (!application) throw new Error('Android manifest has no application');
    application.$['android:usesCleartextTraffic'] = 'true';
    return mod;
  });
};
