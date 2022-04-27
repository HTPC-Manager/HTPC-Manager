function showtime(time){
		var minutes = Math.floor(time / 60) ,
			seconds = Math.floor(time % 60),
			result = (minutes < 10 ? '0' + minutes : minutes) + 'm' + (seconds < 10 ? '0' + seconds : seconds) + 's';
		return result;
}

function vlcSendCmd(cmd){
    $('#vlc-delAll').hide()
    $('#vlc-web').hide()
    $('#vlc-sendCmd').hide()
    $('#vlc-refresh').hide()
    $('#error').hide()
    $('#info').hide()
    $('#info').html('')
    $('#vlc-instances').hide();
    $('#error').html('');
    $('.spinner').show();
    $('#instances-table').html('');
    if (cmd) {cmd = '&vlcCmd=' + encodeURIComponent(cmd)} else {cmd = ''}
    $.get(WEBDIR + 'kodi/vlcSendCmd?serverID=' + $('#servers').val() + cmd + '&autoSelect=0', function(data) {
        if (data==null) {
            $('#error').append('<h4>Unable to contact VLC:</h4><p>We were unable to contact VLC server on ' + $("#servers option:selected" ).text() + '</p>').show()
        } else if (data=='disabled') {
            $('#info').append('<h4>VLC Disabled:</h4><p>VLC server is disabled on ' + $("#servers option:selected" ).text() + '</p>').show()
        } else {
            var len = 0
            for (cmd in data.command){
                if (data.command[cmd]){
                    $('#error').append('<p>' + data.command[cmd] + '</p>')
                    len++
                }
            }
            if (len){$('#error').prepend('<h4>Your command returned a error:</h4>').show()}
            var row = $('<tr>');
            len = 0
            for (instance in data.status){
                len++
                row.append(
                
                    $('<td>').text(instance),
                    $('<td>').html(function(){
                                    var inputs = '<ul>';
                                    for (input in data.status[instance].inputs){inputs += '<li>' + data.status[instance].inputs[input] + '</li>'}
                                    return inputs + '</ul>';
                                }),
                    $('<td>').text(data.status[instance].enabled),
                    $('<td>').text(data.status[instance].state),
                    $('<td>').text(showtime(data.status[instance].length)),
                    $('<td>').text(showtime(data.status[instance].time)),
                    $('<td>').html('<a href="#" data-inst="' + instance + '" id="vlc-del-' + len + '" class="btn ajax-confirm vlc-del" title="Delete"><i class="icon-trash"></i> Delete</a>')
                )
            }
            if (!len) {row.append($('<td>').attr('colspan',7).text('No transcode instances'));}
            $('#instances-table').append(row);
            $('#vlc-instances').show();
            $('.vlc-del').click(function(){vlcSendCmd('del ' + $(this).attr('data-inst'))});
            $('#vlc-delAll').show()
            $('#vlc-web').attr("href", WEBDIR + 'kodi/vlcwebinterface?serverID=' + $('#servers').val()).show()
            $('#vlc-sendCmd').show()
        }
        $('.spinner').hide()
        $('#vlc-refresh').show()
    })
}

$(document).ready(function() {

    $.get(WEBDIR + 'kodi/getserver', function(data) {
        if (data==null) return;
        server = $('<option>').text('Global').val(-1);
        $('#servers').append(server);
        $.each(data.servers, function(i, item) {
            server = $('<option>').text(item.name).val(item.id);
            $('#servers').append(server);
        });
        vlcSendCmd()
    }, 'json');

    $('#servers').change(function(){vlcSendCmd()});
    $('#vlc-sendCmd').click(function(){msg = prompt("Message"); if (msg){vlcSendCmd(msg)}});
    $('#vlc-refresh').click(function(){vlcSendCmd()});
    $('#vlc-delAll').click(function(){vlcSendCmd('del all')});

});