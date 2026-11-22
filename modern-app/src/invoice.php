<?php
// Initial *naive* modernization: copied behavior, without compatibility fix.
// The verifier is expected to detect the genuine PHP 5.6 -> PHP 8.3 difference.
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
$is_walk_in = ((int)$customer == 0);
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
