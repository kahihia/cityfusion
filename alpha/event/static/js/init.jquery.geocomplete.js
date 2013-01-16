(function ($) {    
    $(document).ready(function () {
        var map=$('.location_map');
        function panMapToCenter(lat, lng){
            var point = new google.maps.LatLng(lat, lng);            
            google.maps.event.trigger(map_location, 'resize');
            marker_location.setPosition(point);            
            map_location.panTo(point);
            $("#id_location_lng").val(lng);
            $("#id_location_lat").val(lat);
        }

        //$(choose_location_button).on("click", function(){ panMapToCenter(-40,70) });
        $("#id_place").val("");
        $("#id_place").geocomplete({
                details: ".geo-details",
                detailsAttribute: "data-geo",
                types: ['geocode', 'establishment'],
                componentRestrictions: {country: 'ca'},                
                
            }).bind("geocode:result", function(event, result){            
                $("#id_tags__tagautosuggest")[0].tagspopup.forCity($("#id_geo_city").val());
                panMapToCenter(result.geometry.location.lat(), result.geometry.location.lng());
            });
        
        $("#id_place").on("blur", function(){
            $(".pac-container").removeClass("show");
        });
        $("#id_place").on("focus", function(){
            $(".pac-container").addClass("show");
        });
        setTimeout(function(){
            var newVenue = $("<div>").addClass("new-venue").html("suggest a new venue");
            $(".pac-container").append(newVenue);
            $(newVenue).on("mousedown", function(){
               $(".suggest").show();
               google.maps.event.trigger(map_location, 'resize');
            });
        },1000);
    });
})(jQuery);