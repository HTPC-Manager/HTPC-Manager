var player = "";
var unloaded = false;

function vlcProxy(vlcCmd){
    if (transcode > 0){
         if (vlcCmd) {
            vlcCmd = '&vlcCmd=' + encodeURIComponent(vlcCmd)
         } else {
            vlcCmd = ''
         }
         $.ajax({
          dataType: "json",
          url: WEBDIR + 'kodi/vlcSendCmd?serverID=' + serverID + vlcCmd,
          success: function(data){
            if (!unloaded){
                player.options.duration = data.status[uniqueID]['length']
            }
          }
        });
    }
}

function doResize(subsOnly){
    
    var playerW = $('.content').outerWidth(true);
    var playerH = $('.content').outerHeight(true);
    
    if (!subsOnly && player.media.pluginApi != null && player.media.pluginApi.setVideoSize) {
        player.media.pluginApi.setVideoSize(playerW, playerH)
    }
    
    if ($('.mejs-captions-position').length) {
        videoH = playerH
        if ((playerW / playerH) < 1.33) {videoH = playerW * 0.75;}
        lineS = videoH / 12
        subBottom = ((playerH - videoH)/2)
        if (subBottom < 35){subBottom = 35}
        $('.mejs-captions-position').css('bottom', parseInt(subBottom) + 'px');
        $('.mejs-captions-position').css('line-height', parseInt(lineS) + 'px');
        $('.mejs-captions-position').css('font-size', parseInt(lineS * 0.75) + 'px');
    }
    
}

$(document).ready(function() {
    player = new MediaElementPlayer('#player', {
            mode: mode,
            plugins: plugins,
            pluginPath: WEBDIR + "js/libs/mediaelement/",
            flashName: "flashmediaelement-cdn.swf",
            defaultVideoWidth: '100%',
            defaultVideoHeight: '100%',
            videoWidth: '100%',
            videoHeight: '100%',
            enableAutosize: true,
            setDimensions: false,
            audioWidth: 400,
            audioHeight: 30,
            startVolume: 1,
            loop: false,
            alwaysShowControls: false,
            iPadUseNativeControls: false,
            iPhoneUseNativeControls: false, 
            AndroidUseNativeControls: false,
            alwaysShowHours: false,
            enableKeyboard: false,
            pauseOtherPlayers: true,
            features: features,
            qualities: qualities,
            defaultquality: quality,
            usePluginFullScreen: false,
            keyActions: [],
            success: function(){vlcProxy(''); doResize(true)},
            duration: duration,
            customError: '<a href="">Download</a><BR />'
    });
    $(window).resize(function(){doResize(false)});
});
window.onunload = function(){
  if (!unloaded && transcode > 0){
    unloaded = true;
    vlcProxy('del ' + uniqueID);
  }
};
window.onbeforeunload = function(){
  if (!unloaded && transcode > 0){
    unloaded = true;
    vlcProxy('del ' + uniqueID);
  }
};
