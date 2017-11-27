var x = 1;
var y;
var z;
var w;
var v;

(function() {
    function totalRand(x) {
        var x = 2;
        if (x == 0) {
            return 1;
        } else if (x == 1) {
            return 2;
        } else {
            return 3;
        }
    }


    function add2(x) {
        x = x + 2;
        return x;
    }

    function multiply(x, y) {
        return x * y;
    }

    function multiply3(x, y, z) {
        var a = x;
        var b = y;
        var c = z;
        return a * b * c;
    }

    x = totalRand(123);
    x = x + 2;

    y = 1 + add2(2);
    y = add2(4);

    z = y + x;
    y = z + x;

    z = multiply(x, y);
    y = x + y + z;

    y = multiply3(x, y, z)

    if (x > 3 && y > 100) {
        w = -1;
    } else if (x < 3 && y < 0) {
        w = -100;
    } else {
        w = -1000;
    }

    var i = 0;
    v = 0;
    while ( i < 10 && v < 300) {
        i = i + 1;
        v = i;
    }

    while ( i < 20 && v < 300 && v != -1 ) {
        i = i + 1;
        v = v + i;
    }

    while ( i < 30 && v < 300 ) {
        i = i + 1;
        v = v + i;
    }

})();

