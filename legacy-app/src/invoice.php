<?php
// Representative legacy invoicing program created for this hackathon.
// Its PHP 5.6 loose-comparison behavior is intentional training material.
$input = json_decode(stream_get_contents(STDIN), true);
if (!is_array($input)) {
    fwrite(STDERR, "Expected JSON object\n");
    exit(2);
}
$amount = isset($input['amount_cents']) ? (int)$input['amount_cents'] : 0;
$customer = isset($input['customer_id']) ? $input['customer_id'] : 'guest';
if ($amount < 0) {
    echo json_encode(array('ok' => false, 'error' => 'negative_amount')) . "\n";
    exit(0);
}
// PHP 5.6: a non-numeric string such as "guest" compares equal to 0.
// PHP 8.3: it does NOT. This produces a genuine migration regression.
$is_walk_in = ($customer == 0);
$handling = $is_walk_in ? 0 : 50;
$subtotal = $amount + $handling;
$tax = (int)floor($subtotal * 0.05 + 0.5);
echo json_encode(array(
    'ok' => true,
    'customer_id' => $customer,
    'walk_in' => $is_walk_in,
    'handling_cents' => $handling,
    'tax_cents' => $tax,
    'total_cents' => $subtotal + $tax
)) . "\n";
